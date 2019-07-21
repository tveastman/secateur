DONE
====
- Replace the user proxy model with an actual user model based on AbstractUser
- A FormView for triggering a blocking run.
- A sloppy initial deployment
- Homepage
- Gunicorn
- A daily scheduled job for triggering unblocking.
- Add a mechanism to make sure secateur doesn't do anything if the user account no longer works.
- Set up a dockerfile to build an image for the app
- Set up a docker-compose to build a dev environment
- A 'disconnect from secateur' page that removes secateur's ability to act as you.
- A management command that upgrades someone to superuser
- A warning on the frontpage for when the twitter API hasn't been enabled for you.
- An admin action that will call 'get_user' on accounts.


NOW
===
- Add an account detail view.
- Add a search page to look up a user.


NEXT
====


BACKLOG
=======
- Login page
- Add a random margin to the blocking duration.
- move all the celery tasks into celery.py
- Write copy for the frontpage explaining what the tool actually does.
- Add a search bar.
- Add a rest API
- Replace the current blocking mechanism with a 'Job' model than can be used
  to arbitrarily schedule block, unblock, mute, and unmute operations.
