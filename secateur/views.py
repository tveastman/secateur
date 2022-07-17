from typing import Any, Optional, Dict
import datetime
import logging

import django.db.models
import django.forms
import django.http
import structlog
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import QuerySet, F, Q
from django.db.models.functions import Now, Random
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.timezone import now
from django.views.generic import DetailView, FormView, ListView, TemplateView
from waffle.mixins import WaffleFlagMixin
from waffle import flag_is_active

from . import forms, models, tasks, otel

logger = structlog.get_logger(__name__)


class Home(TemplateView):
    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        otel.homepage_counter.add(1)
        return super().get_context_data(**kwargs)

    template_name = "home.html"


class Account(DetailView):
    template_name = "account.html"
    model = models.Account

    def get_object(
        self, queryset: Optional[django.db.models.query.QuerySet] = None
    ) -> django.db.models.Model:
        return self.get_queryset().get(screen_name=self.kwargs["screen_name"])


class LogMessages(LoginRequiredMixin, ListView):
    template_name = "log-messages.html"
    model = models.LogMessage
    paginate_by = 50

    def get_queryset(self) -> django.db.models.query.QuerySet:
        user = models.User.objects.get(pk=self.request.user.pk)
        return (
            models.LogMessage.objects.filter(user=user)
            .exclude(
                action__in=[
                    models.LogMessage.Action.CREATE_BLOCK,
                    models.LogMessage.Action.DESTROY_BLOCK,
                    models.LogMessage.Action.CREATE_MUTE,
                    models.LogMessage.Action.DESTROY_MUTE,
                ]
            )
            .order_by("-id")
        )


class BlockMessages(LoginRequiredMixin, ListView):
    template_name = "block-messages.html"
    model = models.LogMessage
    paginate_by = 500

    def get_queryset(self) -> django.db.models.query.QuerySet:
        user = models.User.objects.get(pk=self.request.user.pk)
        return models.LogMessage.objects.filter(user=user).order_by("-id")


class Blocked(LoginRequiredMixin, ListView):
    template_name = "blocked.html"
    paginate_by = 200

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form"] = forms.Search(self.request.GET)
        return context

    def get_queryset(self) -> QuerySet[models.Relationship]:
        form = forms.Search(self.request.GET)
        relationships = models.Relationship.objects.select_related("object").filter(
            subject_id=self.request.user.account_id, type=models.Relationship.BLOCKS
        )
        if form.is_valid():
            relationships = relationships.filter(
                object__screen_name__istartswith=form.cleaned_data["screen_name"]
            )
        return relationships


class UnblockEverybody(LoginRequiredMixin, FormView):
    """Allow a user to set the 'blocked until' to within the next month."""

    form_class = forms.UnblockEverybody
    template_name = "unblock-everybody.html"
    success_url = reverse_lazy("blocked")

    def form_valid(self, form: django.forms.BaseForm) -> django.http.HttpResponse:
        # The form has nothing in it, it's just intercepting POST requests.
        # I guess I could an 'are you sure?' boolean in the form or something.
        user = self.request.user
        unblock_time = datetime.timedelta(days=28)

        updated = (
            models.Relationship.objects.filter(
                subject_id=user.account_id,
                type__in=[models.Relationship.BLOCKS, models.Relationship.MUTES],
            )
            .filter(Q(until__isnull=True) | Q(until__gt=Now() + unblock_time))
            .update(until=Now() + (Random() * datetime.timedelta(days=28)))
        )

        models.LogMessage.objects.create(
            time=now(), action=models.LogMessage.Action.UNBLOCK_EVERYBODY, user=user
        )

        messages.add_message(
            self.request,
            messages.INFO,
            f"You've scheduled the "
            f"unblocking of {updated} accounts within the next 28 days.",
        )

        return super().form_valid(form)


class Search(LoginRequiredMixin, FormView):
    form_class = forms.Search
    template_name = "search.html"
    success_url = reverse_lazy("search")

    ## TODO: check user has API enabled.

    def form_valid(self, form: django.forms.BaseForm) -> django.http.HttpResponse:
        screen_name = form.cleaned_data["screen_name"]
        account = None

        # First search our local database.
        try:
            account = models.Account.objects.get(screen_name__iexact=screen_name)
        except models.Account.DoesNotExist:
            logger.debug("Account not found for user: %s", screen_name)
        if account is None:
            account = tasks.get_user(self.request.user.pk, screen_name=screen_name)

        if account is None:
            messages.add_message(
                self.request, messages.INFO, "No account by that name found."
            )
            return super().form_valid(form)

        self.success_url = reverse(
            "account", kwargs={"screen_name": account.screen_name}
        )
        return super().form_valid(form)


class Block(LoginRequiredMixin, FormView):
    form_class = forms.BlockAccountsForm
    template_name = "block.html"
    success_url = reverse_lazy("block-accounts")

    def form_valid(self, form: django.forms.BaseForm) -> django.http.HttpResponse:
        # These limitations will go somewhere better later. On the user model
        # where they can be set per-user.
        TOO_MANY_TO_MUTE = 10_000
        user = models.User.objects.get(pk=self.request.user.pk)
        user_account = user.account

        account = user.get_account_by_screen_name(form.cleaned_data["screen_name"])
        if account is None:
            messages.add_message(
                self.request,
                messages.ERROR,
                "Account not found.",
            )
            return super().form_valid(form)

        messages.add_message(
            self.request,
            messages.INFO,
            "Retrieved account %s from Twitter" % (account,),
        )

        bucket = user.token_bucket
        ## SAFETY GUARDS
        followers_count = account.followers_count or 0
        if form.cleaned_data["block_followers"] and followers_count > bucket.max:
            messages.add_message(
                self.request,
                messages.ERROR,
                "Sorry, {} has too many followers to block them all (max is {:0.0f} for now)".format(
                    account, bucket.max
                ),
            )
            return super().form_valid(form)
        if form.cleaned_data["mute_followers"] and followers_count > TOO_MANY_TO_MUTE:
            messages.add_message(
                self.request,
                messages.ERROR,
                "Sorry, {} has too many followers to mute them all (max is {} for now)".format(
                    account, TOO_MANY_TO_MUTE
                ),
            )
            return super().form_valid(form)

        if account == user_account:
            messages.add_message(
                self.request,
                messages.ERROR,
                "You don't want to block your own account or followers.",
            )
            return super().form_valid(form)

        if flag_is_active(self.request, "check_not_blocked"):
            if (
                form.cleaned_data["block_followers"]
                or form.cleaned_data["mute_followers"]
            ) and user.is_blocked_by(user_id=account.user_id):
                messages.add_message(
                    self.request,
                    messages.INFO,
                    "That account appears to have blocked you, so Secateur can't get their follower list. "
                    "You can still block or mute them, but not their followers.",
                )
                return super().form_valid(form)

        ## RATE LIMIT CHECK
        tokens_required: int = 0
        if form.cleaned_data["block_followers"]:
            tokens_required += followers_count
        if form.cleaned_data["mute_followers"]:
            tokens_required += followers_count
        if tokens_required > user.current_tokens:
            messages.add_message(
                self.request,
                messages.ERROR,
                "Rate limited: Sorry, you can only block a certain number of people per day, you'll "
                "need to try again later. If you're actively being harassed, this limit can be increased "
                "if you contact the administrator.",
            )
            return super().form_valid(form)
        elif tokens_required:
            user.withdraw_tokens(tokens_required)
            user.save(update_fields=("token_bucket_time", "token_bucket_value"))

        WEEK = datetime.timedelta(days=7)
        if form.cleaned_data["duration"]:
            duration = form.cleaned_data["duration"] * WEEK
            until = timezone.now() + duration
        else:
            duration = None
            until = None

        if form.cleaned_data["block_account"]:
            tasks.create_relationship.delay(
                secateur_user_pk=user.pk,
                type=models.Relationship.BLOCKS,
                user_id=account.user_id,
                until=until,
            )
        if form.cleaned_data["mute_account"]:
            tasks.create_relationship.delay(
                secateur_user_pk=user.pk,
                type=models.Relationship.MUTES,
                user_id=account.user_id,
                until=until,
            )
        if form.cleaned_data["mute_followers"]:
            tasks.twitter_block_followers(
                secateur_user=user,
                type=models.Relationship.MUTES,
                account=account,
                duration=duration,
            )
        if form.cleaned_data["block_followers"]:
            tasks.twitter_block_followers(
                secateur_user=user,
                type=models.Relationship.BLOCKS,
                account=account,
                duration=duration,
            )
        return super().form_valid(form)


class Disconnect(LoginRequiredMixin, FormView):
    """Allow a user to erase their credentials on Secateur"""

    form_class = forms.Disconnect
    template_name = "disconnect.html"
    success_url = reverse_lazy("disconnected")

    def form_valid(self, form: django.forms.BaseForm) -> django.http.HttpResponse:
        # The form has nothing in it, it's just intercepting POST requests.
        # I guess I could an 'are you sure?' boolean in the form or something.

        user = self.request.user
        user_social_auth = user.twitter_social_auth  # There can be only one

        # Erase the oauth token we've got.
        user_social_auth.extra_data = None
        user_social_auth.save(update_fields=["extra_data"])

        # Disable the twitter API.
        user.is_twitter_api_enabled = False
        user.oauth_token = None
        user.oauth_token_secret = None
        user.save(
            update_fields=[
                "is_twitter_api_enabled",
                "oauth_token",
                "oauth_token_secret",
            ]
        )

        models.LogMessage.objects.create(
            time=now(), action=models.LogMessage.Action.DISCONNECT, user=user
        )

        # Log the user out.
        logout(self.request)

        return super().form_valid(form)


class Disconnected(TemplateView):
    template_name = "disconnected.html"


class Following(LoginRequiredMixin, ListView):
    template_name = "following.html"

    def get_queryset(self) -> django.db.models.query.QuerySet:
        user = self.request.user
        assert user.account
        return user.account.friends


class UpdateFollowing(LoginRequiredMixin, FormView):
    form_class = forms.UpdateFollowing
    template_name = "update-following.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form: django.forms.BaseForm) -> django.http.HttpResponse:
        user = self.request.user
        tasks.twitter_update_friends(secateur_user=user, get_profiles=True)
        messages.add_message(
            self.request,
            messages.INFO,
            "The list of accounts you follow will update shortly. It may take some time to complete.",
        )
        return super().form_valid(form)
