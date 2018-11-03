from celery import Celery

app = Celery("secateur")
app.config_from_object("django.conf:settings", namespace="CELERY")


@app.task(bind=True)
def debug_task(self):
    result = "Request: {0!r}".format(self.request)
    return result
