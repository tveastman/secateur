DONE
====
- Replace the user proxy model with an actual user model based on AbstractUser
- A FormView for triggering a blocking run.
- A sloppy initial deployment
- Homepage
- Gunicorn
- A daily scheduled job for triggering unblocking.
- Add a mechanism to make sure secateur doesn't do anything if the user account no longer works.


NOW
===
- Add a search page to look up a user.


NEXT
====


BACKLOG
=======
- Add an account detail view.
- Set up a dockerfile to build an image for the app
- Set up a docker-compose to build a dev environment
- Login page
- Add a random margin to the blocking duration.
- move all the celery tasks into celery.py
- Write copy for the frontpage explaining what the tool actually does.
- Add a search bar.
- Add a rest API
- A 'disconnect from secateur' page that removes secateur's ability to act as you.
