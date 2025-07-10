from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from django.http import JsonResponse
import json
from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRolePermission
from ..models import Notification
from ..models import Card
from pymongo import MongoClient
import certifi
import os
from django.utils import timezone
from dotenv import load_dotenv

load_dotenv()  # Load from .env if present

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("TRACKER_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME")
       

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri, tls=True,tlsAllowInvalidCertificates=True,tlsCAFile=certifi.where())

@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_dynamic_notifications(request):
    employee_id = request.data.get('auth-user-id')

    if not employee_id:
        return JsonResponse({'error': 'Employee ID is required.'}, status=400)

    # Fetch notifications directly from the Notification model
    notifications = Notification.objects.filter(employeeId=employee_id).order_by('-created_date')
    
    notification_list = []
    for notification in notifications:
        # Get card details for additional info (optional)
        try:
            card = Card.objects.get(cardId=notification.cardId)
            card_name = card.cardName
            board_id = card.boardId
        except Card.DoesNotExist:
            # Handle case where card might have been deleted
            card_name = "Unknown Card"
            board_id = None
        
        notification_list.append({
            'cardId': notification.cardId,
            'cardName': card_name,
            'boardId': board_id,
            'message': notification.message,
            'is_read': notification.is_read,
            'created_date': notification.created_date
        })

    return JsonResponse(notification_list, safe=False, status=200)


@csrf_exempt
@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def mark_notifications_as_read(request):
    # Get employee_id from request.data
    employee_id = request.data.get('auth-user-id')
    print(f"Employee ID from request.data: {employee_id}")
    print(f"Full request.data: {request.data}")

    if not employee_id:
        return JsonResponse({'error': 'Employee ID is required'}, status=400)

    try:
        # Use direct MongoDB query to avoid Djongo NOT operator issue
        db = client[db_name]
        collection = db['Tracker_notification']  # Your notification collection name
        
        # Get current timestamp
        current_time = timezone.now()
        
        # Update unread notifications directly in MongoDB
        result = collection.update_many(
            {
                'employeeId': employee_id,
                'is_read': False  # Direct boolean comparison works better than NOT
            },
            {
                '$set': {
                    'is_read': True,
                    'lastmodified_date': current_time
                }
            }
        )
        
        updated_count = result.modified_count
        print(f"Updated notifications count: {updated_count}")

        if updated_count == 0:
            return JsonResponse({'message': 'No unread notifications found'}, status=200)

        return JsonResponse({'message': f'{updated_count} notifications marked as read'}, status=200)
        
    except Exception as e:
        print(f"Error updating notifications: {str(e)}")
        return JsonResponse({'error': 'Failed to update notifications'}, status=500)