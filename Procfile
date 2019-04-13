web: gunicorn -k eventlet --log-level debug secateur.wsgi
celery: celery -A secateur worker -l info
