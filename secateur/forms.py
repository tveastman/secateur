from django import forms


class BlockAccountsForm(forms.Form):
    screen_name = forms.CharField(help_text="The Twitter username.")
    duration = forms.IntegerField(min_value=1, max_value=52, initial=12)
    block_account = forms.BooleanField(required=False)
    mute_account = forms.BooleanField(required=False)
    block_followers = forms.BooleanField(required=False)
    mute_followers = forms.BooleanField(required=False)

    
