from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from django.utils import timezone
from django.utils.timezone import now
from pyauth.auth import HasRolePermission
from ..models import Notification, Card
from ..utils.db import get_tracker_db
from ..utils.auth import get_auth_user_id
from ..utils.responses import api_success, api_error
from datetime import timedelta

@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_dynamic_notifications(request):
    employee_id = get_auth_user_id(request)
    if not employee_id:
        return api_error('Employee ID is required.', code="UNAUTHORIZED", status_code=status.HTTP_400_BAD_REQUEST)

    try:
        db = get_tracker_db()
        collection = db['Tracker_notification']
        
        # Fetch unread notifications
        cursor = collection.find({'employeeId': employee_id, 'is_read': False}).sort('created_date', -1)
        filtered = list(cursor)

        # Batch-fetch all referenced cards in one query
        card_ids = {n.get('cardId') for n in filtered if n.get('cardId')}
        cards_by_id = {
            card.cardId: card
            for card in Card.objects.filter(cardId__in=card_ids)
        }

        # Build response
        notification_list = []
        for n in filtered:
            card = cards_by_id.get(n.get('cardId'))
            if card:
                card_name = card.cardName
                board_id = card.boardId
            else:
                card_name = "Unknown Card"
                board_id = None

            notification_list.append({
                'id': str(n.get('_id')),
                'cardId': n.get('cardId'),
                'cardName': card_name,
                'boardId': board_id,
                'message': n.get('message'),
                'is_read': n.get('is_read', False),
                'created_date': n.get('created_date'),
                'lastmodified_date': n.get('lastmodified_date'),
            })

        return api_success(notification_list)
    except Exception as e:
        return api_error(f'Failed to fetch notifications: {str(e)}', code="SERVER_ERROR", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['PATCH'])
@permission_classes([HasRolePermission])
def mark_notifications_as_read(request):
    employee_id = get_auth_user_id(request)
    if not employee_id:
        return api_error('Employee ID is required', code="UNAUTHORIZED", status_code=status.HTTP_400_BAD_REQUEST)

    try:
        db = get_tracker_db()
        collection = db['Tracker_notification']
        current_time = timezone.now()
        result = collection.update_many(
            {'employeeId': employee_id, 'is_read': False},
            {'$set': {'is_read': True, 'lastmodified_date': current_time}}
        )

        updated_count = result.modified_count
        if updated_count == 0:
            return api_success(message='No unread notifications found')

        return api_success(message=f'{updated_count} notifications marked as read')
    except Exception as e:
        return api_error(f'Failed to update notifications: {str(e)}', code="SERVER_ERROR", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def clear_notifications(request):
    employee_id = get_auth_user_id(request)
    if not employee_id:
        return api_error('Employee ID is required', code="UNAUTHORIZED", status_code=status.HTTP_400_BAD_REQUEST)

    try:
        db = get_tracker_db()
        collection = db['Tracker_notification']
        current_time = timezone.now()
        result = collection.update_many(
            {'employeeId': employee_id, 'is_read': False},
            {'$set': {'is_read': True, 'lastmodified_date': current_time}}
        )
        
        return api_success(message=f'{result.modified_count} notifications cleared')
    except Exception as e:
        return api_error(f'Failed to clear notifications: {str(e)}', code="SERVER_ERROR", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

@csrf_exempt
@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def clear_single_notification(request, notification_id):
    employee_id = get_auth_user_id(request)
    if not employee_id:
        return api_error('Employee ID is required', code="UNAUTHORIZED", status_code=status.HTTP_400_BAD_REQUEST)

    try:
        from bson.objectid import ObjectId
        db = get_tracker_db()
        collection = db['Tracker_notification']
        
        try:
            obj_id = ObjectId(notification_id)
        except Exception:
            return api_error('Invalid Notification ID format', code="BAD_REQUEST", status_code=status.HTTP_400_BAD_REQUEST)

        result = collection.update_one(
            {'_id': obj_id, 'employeeId': employee_id},
            {'$set': {'is_read': True, 'lastmodified_date': timezone.now()}}
        )
        
        if result.matched_count == 0:
            return api_error('Notification not found', code="NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND)

        return api_success(message='Notification cleared')
    except Exception as e:
        return api_error(f'Failed to clear notification: {str(e)}', code="SERVER_ERROR", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
