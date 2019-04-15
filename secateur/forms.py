from django import forms


class BlockAccountsForm(forms.Form):
    screen_name = forms.CharField(help_text="The Twitter username.")
    duration = forms.IntegerField(
        min_value=1, max_value=52, initial=6,
        help_text="How long to block the accounts (in weeks)"
    )
    block_account = forms.BooleanField(required=False)
    mute_account = forms.BooleanField(required=False)
    block_followers = forms.BooleanField(required=False)
    mute_followers = forms.BooleanField(required=False)
