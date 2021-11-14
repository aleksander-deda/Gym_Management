import os
from notifications.config import get_notification_count, run_notifier
from django.core.wsgi import get_wsgi_application
run_notifier()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "gym.settings")

application = get_wsgi_application()
