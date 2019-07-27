# Secateur

Secateur is a web app that allows you to temporary block or mute a Twitter account, *and* all their followers.

It's hosted at https://secateur.app

People who want to use Secateur can either use the public app or, if their privacy and security needs necessitate it, they can run their own instance by following these instructions.

## Setting up your own environment.

To run your own instance of Secateur, you need the following:

- recent versions of `docker` and `docker-compose`
- credentials for the [Twitter Developer API](https://developer.twitter.com/)

If you have those, setting up your developer environment should be straightforward:

1. Clone this repository.
2. Copy `.env-template` to `.env` and add your Twitter API credentials.
3. Run `docker-compose up`.

That, actually, ought to be all there is to it. Once the docker containers are running, you can go to `http://localhost:5000` and hopefully see the Secateur home page. If your Twitter Developer API stuff is set up, you should be able to log in to your own Secateur environment.

Once you've logged in, you'll probably want to upgrade your account to be the superuser:

```$ docker-compose exec app ./manage.py promotesuperuser ${MY_TWITTER_ACCOUNT}```
