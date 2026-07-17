import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Tracker_backend.settings')
django.setup()
from Tracker.models import Notification
n = Notification.objects.last()
print(f"n.id: {getattr(n, 'id', None)}, n.pk: {getattr(n, 'pk', None)}")
