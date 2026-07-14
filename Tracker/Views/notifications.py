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

    # Batch-fetch all referenced cards in one query instead of one query per notification
    card_ids = {n.cardId for n in filtered if n.cardId}
    cards_by_id = {
        card.cardId: card
        for card in Card.objects.filter(cardId__in=card_ids)
    }

    # Build response
    notification_list = []
    for notification in filtered:
        card = cards_by_id.get(notification.cardId)
        if card:
            card_name = card.cardName
            board_id = card.boardId
        else:
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

    return api_success(notification_list)

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
