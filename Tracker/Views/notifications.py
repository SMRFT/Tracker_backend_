
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from django.http import JsonResponse
import json

from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRoleAndDataPermission
from ..auth.permissions import SkipPermissionsIfDisabled

# Models and serializers
from ..models import Notification
from ..models import Card





@api_view(['GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def get_dynamic_notifications(request):
    employee_id = request.GET.get('employeeId')

    if not employee_id:
        return JsonResponse({'error': 'Employee ID is required.'}, status=400)

    # Fetch cards where the employee is a member
    recent_memberships = []
    for card in Card.objects.all():
        members = card.members  # Assuming members is a list or None
        if members:
            if any(member.get('employeeId') == employee_id for member in members):
                # Compare the createdDate/createdTime or some logic to see if this is a "new" membership
                recent_memberships.append({
                    'cardId': card.cardId,
                    'cardName': card.cardName,
                    'boardId': card.boardId,
                    'message': f"You've been added to the card '{card.cardName}'."
                })

    # Return the recent memberships as dynamic notifications
    return JsonResponse(recent_memberships, safe=False, status=200)





@csrf_exempt
@api_view(['PATCH'])  # Change to PUT or PATCH
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def mark_notifications_as_read(request):
    try:
        data = json.loads(request.body)

        if not data:
            return JsonResponse({'error': 'Request body is empty'}, status=400)

        employee_id = data.get("employeeId")

        if not employee_id:
            return JsonResponse({'error': 'Employee ID is required'}, status=400)

        # Update notifications
        updated_count = Notification.objects.filter(employeeId=employee_id, is_read=False).update(is_read=True)

        if updated_count == 0:
            return JsonResponse({'message': 'No unread notifications found'}, status=200)

        return JsonResponse({'message': f'{updated_count} notifications marked as read'}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)

    except Exception as e:
        return JsonResponse({'error': f'Unexpected error: {str(e)}'}, status=500)