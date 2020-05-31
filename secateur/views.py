from typing import Any, Optional
import datetime
import logging

import django.db.models
import django.forms
import django.http
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, TemplateView

from . import forms, models, tasks

logger = logging.getLogger(__name__)


class Home(TemplateView):
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
        return models.LogMessage.objects.filter(user=user).order_by("-time")


class Search(LoginRequiredMixin, FormView):
    form_class = forms.Search
    template_name = "search.html"
    success_url = reverse_lazy("search")

    ## TODO: check user has API enabled.

    def form_valid(self, form: django.forms.BaseForm) -> django.http.HttpResponse:
        screen_name = form.cleaned_data["screen_name"]
        screen_name_lower = screen_name.lower()
        account = None

        # First search our local database.
        try:
            account = models.Account.objects.get(screen_name_lower=screen_name_lower)
        except models.Account.DoesNotExist:
            logger.debug("Account not found for user: %s", screen_name_lower)
        if account is None:
            account = tasks.get_user(
                self.request.user.pk, screen_name=screen_name_lower
            )

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
        TOO_MANY_TO_BLOCK = 100_000
        TOO_MANY_TO_MUTE = 5_000
        user = models.User.objects.get(pk=self.request.user.pk)
        user_account = user.account

        account = user.get_account_by_screen_name(form.cleaned_data["screen_name"])
        # messages.add_message(self.request, messages.INFO, "Retrieved account %s from Twitter" % (account,))
        profile = account.profile
        if not profile:
            account = tasks.get_user(user.pk, user_id=account.pk)
            profile = account.profile
            logger.debug("Retrieved account %s and profile %s", account, profile)
        messages.add_message(
            self.request,
            messages.INFO,
            "Retrieved account %s from Twitter" % (account,),
        )

        ## SAFETY GUARDS
        assert profile is not None
        followers_count = profile.json.get("followers_count", 0)
        if form.cleaned_data["block_followers"] and followers_count > TOO_MANY_TO_BLOCK:
            messages.add_message(
                self.request,
                messages.ERROR,
                "Sorry, {} has too many followers to block them all (max is {} for now)".format(
                    account, TOO_MANY_TO_BLOCK
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
        user_social_auth = user.twitter_social_auth()  # There can be only one

        # Erase the oauth token we've got.
        user_social_auth.extra_data = None
        user_social_auth.save(update_fields=["extra_data"])

        # Disable the twitter API.
        user.is_twitter_api_enabled = False
        user.save(update_fields=["is_twitter_api_enabled"])

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
