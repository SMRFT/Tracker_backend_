from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from pyauth.auth import HasRolePermission
from datetime import timedelta
import pytz

from ..models import Card
from .email_utils import send_card_notification_email
from ..utils.db import get_global_db
from ..utils.auth import get_auth_user_id
from ..utils.responses import api_success, api_error
from ..utils.members import parse_members

@csrf_exempt
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_all_employees(request):
    """
    Get all employee profiles with department and designation names resolved.
    """
    try:
        db = get_global_db()
        profiles = db['backend_diagnostics_profile']
        departments = db['backend_diagnostics_Departments']
        designations = db['backend_diagnostics_Designation']

        # Allowed roles for filtering
        allowed_roles = ["ST-R-A", "ST-R-EMP", "ST-R-HOD"]

        # MongoDB query: match if primaryRole OR additionalRoles contain any allowed role
        query = {
            "$or": [
                {"primaryRole": {"$in": allowed_roles}},
                {"additionalRoles": {"$in": allowed_roles}}
            ]
        }

        # Fetch only filtered employees
        employees = list(profiles.find(query, {
            'employeeId': 1,
            'employeeName': 1,
            'department': 1,
            'designation': 1,
            '_id': 0,
            'email': 1
        }))

        dept_map = {d['department_code']: d['department_name'] for d in departments.find({'is_active': True})}
        desig_map = {d['Designation_code']: d['designation'] for d in designations.find({'is_active': True})}

        for emp in employees:
            emp['department'] = dept_map.get(emp['department'], emp['department'])
            emp['designation'] = desig_map.get(emp['designation'], emp['designation'])

        return api_success(employees)

    except Exception as e:
        return api_error(str(e), code="SERVER_ERROR", status_code=500)

@csrf_exempt
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([HasRolePermission])
def add_member_to_card(request):
    """
    Add or remove members to/from a card.
    """
    card_id = request.data.get('cardId') or request.query_params.get('cardId')
    board_id = request.data.get('boardId') or request.query_params.get('boardId')

    try:
        if board_id:
            card = Card.objects.get(cardId=card_id, boardId=board_id)
        else:
            card = Card.objects.filter(cardId=card_id).first()
            if not card:
                raise Card.DoesNotExist
    except Card.DoesNotExist:
        return api_error('Card not found.', code="NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return api_success(card.members or [])

    if request.method == 'POST':
        employee_id = request.data.get('employeeId')
        employee_name = request.data.get('employeeName')
        department = request.data.get('department')

        if not employee_id or not employee_name:
            return api_error('Employee ID and name are required.', code="INVALID_PAYLOAD", status_code=status.HTTP_400_BAD_REQUEST)

        if not card.members:
            card.members = []

        if any(m['employeeId'] == employee_id for m in card.members):
            return api_error('This member is already added to the card.', code="DUPLICATE_MEMBER", status_code=status.HTTP_400_BAD_REQUEST)

        card.members.append({
            'employeeId': employee_id,
            'employeeName': employee_name,
            'department': department,
        })
        card.lastmodified_by = employee_id
        card.lastmodified_date = timezone.now() 
        card.save()

        # Send email notification to the new member
        try:
            db = get_global_db()
            profiles = db['backend_diagnostics_profile']
            new_member = [{'employeeId': employee_id, 'employeeName': employee_name}]
            send_card_notification_email(card, new_member, profiles, action_type="added")
        except Exception as e:
            print(f"Error triggering email in add_member_to_card: {e}")

        return api_success(message='Member added successfully!', status_code=status.HTTP_201_CREATED)

    if request.method == 'DELETE':
        employee_id = request.query_params.get('employeeId')

        if not card.members or not any(m['employeeId'] == employee_id for m in card.members):
            return api_error('Member not found in the card.', code="NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND)

        removed_member = [m for m in card.members if m['employeeId'] == employee_id]
        card.members = [m for m in card.members if m['employeeId'] != employee_id]
        card.save()

        # Send email notification to the removed member
        if removed_member:
            try:
                db = get_global_db()
                profiles = db['backend_diagnostics_profile']
                send_card_notification_email(card, removed_member, profiles, action_type="removed")
            except Exception as e:
                print(f"Error triggering email in add_member_to_card (delete): {e}")

        return api_success(message='Member removed successfully!')


@csrf_exempt
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_board_employees(request, board_id):
    """
    EXCLUDE:
    - columnId == 'done'
    - lastmodified_date OLDER than 7 days

    INCLUDE:
    - recent DONE cards
    - all non-DONE cards
    """
    try:
        # 🔑 Use UTC for comparison
        utc_now = timezone.now().astimezone(pytz.UTC)
        one_week_ago = utc_now - timedelta(days=7)

        # ✅ EXCLUDE only OLD done cards
        cards = Card.objects.filter(boardId=board_id).exclude(
            columnId="done",
            lastmodified_date__lt=one_week_ago
        )
        
        employees = set()

        for card in cards:
            members = parse_members(card.members)

            for m in members:
                employees.add(
                    (str(m.get("employeeId")), m.get("employeeName")),
                )

        employee_list = [
            {"employeeId": eid, "employeeName": name}
            for eid, name in employees
        ]
        
        return api_success({"employees": employee_list})

    except Exception as e:
        return api_error(str(e), code="SERVER_ERROR", status_code=500)

def get_users_for_deadline_mail():
    """
    Fetch users who have any of these roles
    in primaryRole OR additionalRoles.
    """
    try:
        db = get_global_db()
        profiles = db['backend_diagnostics_profile']

        allowed_roles = ["ST-R-EMP", "ST-R-HOD", "ST-R-A", "ST-R-SA"]

        users = list(profiles.find({
            "$or": [
                {"primaryRole": {"$in": allowed_roles}},
                {"additionalRoles": {"$in": allowed_roles}}
            ],
            "email": {"$exists": True}
        }))

        return users

    except Exception as e:
        print(f"Error fetching users: {str(e)}")
        return []
