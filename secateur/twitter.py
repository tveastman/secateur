from social_core.backends.oauth import BaseOAuth2


class TwitterOauth2(BaseOAuth2):
    name = "twitter2"
    AUTHORIZATION_URL = "https://twitter.com/i/oauth2/authorize"
    ACCESS_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
    REFRESH_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
    ACCESS_TOKEN_METHOD = 'POST'
    SCOPE_SEPARATOR = " "
    REDIRECT_STATE = False
    STATE_PARAMETER = True
    USE_BASIC_AUTH = True

    def auth_params(self, state=None):
        params = super().auth_params(state=state)
        #params["code_challenge"] = "challenge"
        params["code_challenge_method"] = "plain"
        print(params)
        return params

    def auth_complete_params(self, state=None):
        params = super().auth_complete_params(state=state)
        params["code_verifier"] = "challenge"
        return params

    def user_data(self, access_token, *args, **kwargs):
        print(f"user_data({access_token=}, {args=}, {kwargs=})")
        headers = {"Authorization": f"Bearer {access_token}"}
        result = self.request(
            'https://api.twitter.com/2/users/me',
            headers=headers
        ).json()
        return result

    def get_user_details(self, response):
        """Return user details from Twitter account"""
        print(f"{response=}")
        return {'username': response['data']['username']}
