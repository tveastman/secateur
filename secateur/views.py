import logging
import datetime

from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView
from django.views.generic.list import ListView
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.utils import timezone

from . import forms
from . import tasks
from . import models

logger = logging.getLogger(__name__)

class Home(TemplateView):
    template_name = "home.html"

@method_decorator(login_required, name='dispatch')
class LogMessages(ListView):
    template_name = "log-messages.html"
    model = models.LogMessage
    paginate_by = 50

    def get_queryset(self):
        user = models.User.objects.get(pk=self.request.user.pk)
        return models.LogMessage.objects.filter(user=user).order_by('-time')

@method_decorator(login_required, name='dispatch')
class BlockAccounts(FormView):
    form_class = forms.BlockAccountsForm
    template_name = "block-accounts.html"
    success_url = "/block-accounts/"

    def form_valid(self, form):
        user = models.User.objects.get(pk=self.request.user.pk)

        account = user.get_account_by_screen_name(form.cleaned_data['screen_name'])
        messages.add_message(self.request, messages.INFO, "Retrieved account %s from Twitter" % (account,))

        WEEK = datetime.timedelta(days=7)
        duration = form.cleaned_data['duration'] * WEEK
        until = timezone.now() + duration

        if form.cleaned_data['block_account']:
            tasks.create_relationship.delay(
                secateur_user_pk=user.pk,
                type=models.Relationship.BLOCKS,
                user_id=account.user_id,
                until=until)
        if form.cleaned_data['mute_account']:
            tasks.create_relationship.delay(
                secateur_user_pk=user.pk,
                type=models.Relationship.MUTES,
                user_id=account.user_id,
                until=until
            )
        if form.cleaned_data['mute_followers']:
            tasks.twitter_block_followers(
                secateur_user=user,
                type=models.Relationship.MUTES,
                account=account,
                until=until
            )
        if form.cleaned_data['block_followers']:
            tasks.twitter_block_followers(
                secateur_user=user,
                type=models.Relationship.BLOCKS,
                account=account,
                until=until
            )
        return super().form_valid(form)
