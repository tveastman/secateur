import celery

app = celery.Celery("secateur")
app.config_from_object("django.conf:settings", namespace="CELERY")


@app.task(bind=True)
def debug_task(self: celery.Task) -> str:
    result = "Request: {0!r}".format(self.request)
    return result
