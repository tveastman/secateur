Why use kanban when you can just move bullet points around a text file?

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
- Add an account detail view.
- Add a search page to look up a user.
- Write copy for the frontpage explaining what the tool actually does.
- Add a page that allows you to update the list of people you follow.
- Add mypy annotation checking
- Upgrade to python 3.8
- Create a token bucket rate limiting system so that no single person can queue up too many blocks at once.
- upgrade all dependencies
- upgrade to django 4
- upgrade to postgresql 14
- Add opentelemetry tracing:
  - ...to the django views
  - ...to the celery tasks
  - ...to the SQL queries
- Add a random margin to the blocking duration.
- add opentelemetry metrics
- create a page that lists everyone you've blocked, with a search mechanism
- find a way to get rid of the 'until' for all secateur users who don't use it anymore or don't exist at all on twitter.

NOW
===


NEXT
====
- create an 'unblock everybody' function

BACKLOG
=======

- Make sure *all* logs are emitted as json blobs.
- simplify the create-relationship task so it doesn't allow screen_name
- Add a search bar.
- put a 'block/mute' form on an account profile page (where a search result sends you.)
- add security.txt
- Login page
- move all the celery tasks into celery.py
- Add a rest API
- Replace the current blocking mechanism with a 'Job' model than can be used
  to arbitrarily schedule block, unblock, mute, and unmute operations. This
  would make the whole thing a whole lot more RESTful.
