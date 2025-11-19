from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from django.http import JsonResponse
from django.utils import timezone
from django.utils.timezone import now
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from pyauth.auth import HasRolePermission
from ..models import Notification, Card
from pymongo import MongoClient
import certifi
import os
from dotenv import load_dotenv
from datetime import timedelta
from django.db.models import Q

load_dotenv()  # Load environment variables from .env

# âœ… Load environment config
env_type = os.environ.get("ENV_CLASSIFICATION", "local")
mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME", 'Tracker')

# âœ… MongoDB Connection
if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri)

db = client[db_name]
tasks_collection = db["tasks"]

# ===========================================================
# âœ… 1. Dynamic Notifications Endpoints
# ===========================================================

@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_dynamic_notifications(request):
    employee_id = request.data.get('auth-user-id')
    if not employee_id:
        return JsonResponse({'error': 'Employee ID is required.'}, status=400)

    two_days_ago = now() - timedelta(days=2)

    # Load all notifications for user (Mongo has no problem)
    all_notifs = Notification.objects.filter(employeeId=employee_id)

    # Now apply your conditions in Python (Djongo-safe)
    filtered = []
    for n in all_notifs:
        if not n.is_read:
            filtered.append(n)
        else:
            if n.lastmodified_date and n.lastmodified_date >= two_days_ago:
                filtered.append(n)

    # Sort by created_date desc (Python sort)
    filtered.sort(key=lambda x: x.created_date, reverse=True)

    # Build response
    notification_list = []
    for notification in filtered:
        try:
            card = Card.objects.get(cardId=notification.cardId)
            card_name = card.cardName
            board_id = card.boardId
        except Card.DoesNotExist:
            card_name = "Unknown Card"
            board_id = None

        notification_list.append({
            'cardId': notification.cardId,
            'cardName': card_name,
            'boardId': board_id,
            'message': notification.message,
            'is_read': notification.is_read,
            'created_date': notification.created_date,
            'lastmodified_date': notification.lastmodified_date,
        })

    return JsonResponse(notification_list, safe=False, status=200)

@csrf_exempt
@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def mark_notifications_as_read(request):
    employee_id = request.data.get('auth-user-id')
    if not employee_id:
        return JsonResponse({'error': 'Employee ID is required'}, status=400)

    try:
        collection = db['Tracker_notification']
        current_time = timezone.now()
        result = collection.update_many(
            {'employeeId': employee_id, 'is_read': False},
            {'$set': {'is_read': True, 'lastmodified_date': current_time}}
        )

        updated_count = result.modified_count
        if updated_count == 0:
            return JsonResponse({'message': 'No unread notifications found'}, status=200)

        return JsonResponse({'message': f'{updated_count} notifications marked as read'}, status=200)
    except Exception as e:
        return JsonResponse({'error': f'Failed to update notifications: {str(e)}'}, status=500)

