web: gunicorn -k eventlet --log-level debug secateur.wsgi
celery: celery -A secateur worker -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler --beat
