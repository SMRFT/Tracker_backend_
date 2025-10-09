import os
import json
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import send_mail

from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view

from ..models import Card

# Load environment variables
load_dotenv()
env_type = os.environ.get("ENV_CLASSIFICATION", "local")
mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("GLOBAL_DB_NAME", "Global")

# Setup MongoDB connection
if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(
        mongo_uri,
        tls=True,
        tlsAllowInvalidCertificates=True,
        tlsCAFile=certifi.where()
    )

@csrf_exempt
@api_view(['GET'])
def get_all_employees(request):
    """
    Get all employee profiles with department and designation names resolved.
    """
    try:
        db = client[db_name]
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

        return JsonResponse(employees, safe=False)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@api_view(['GET', 'POST', 'DELETE'])
def add_member_to_card(request):
    """
    Add or remove members to/from a card.
    """
    card_id = request.data.get('cardId') or request.query_params.get('cardId')

    try:
        card = Card.objects.get(cardId=card_id)
    except Card.DoesNotExist:
        return Response({'error': 'Card not found.'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(card.members or [], status=status.HTTP_200_OK)

    if request.method == 'POST':
        employee_id = request.data.get('employeeId')
        employee_name = request.data.get('employeeName')
        department=request.data.get('department')

        if not employee_id or not employee_name:
            return Response({'error': 'Employee ID and name are required.'}, status=status.HTTP_400_BAD_REQUEST)

        if not card.members:
            card.members = []

        if any(m['employeeId'] == employee_id for m in card.members):
            return Response({'error': 'This member is already added to the card.'}, status=status.HTTP_400_BAD_REQUEST)

        card.members.append({
            'employeeId': employee_id,
            'employeeName': employee_name,
            'department':department,
        })
        card.save()

        return Response({'message': 'Member added successfully!'}, status=status.HTTP_201_CREATED)

    if request.method == 'DELETE':
        employee_id = request.query_params.get('employeeId')

        if not card.members or not any(m['employeeId'] == employee_id for m in card.members):
            return Response({'error': 'Member not found in the card.'}, status=status.HTTP_404_NOT_FOUND)

        card.members = [m for m in card.members if m['employeeId'] != employee_id]
        card.save()

        return Response({'message': 'Member removed successfully!'}, status=status.HTTP_200_OK)

@csrf_exempt
@api_view(['GET'])
def get_board_employees(request, board_id):
    """
    Get a unique list of employees from all cards under a board.
    """
    try:
        cards = Card.objects.filter(boardId=board_id)
        employees = set()

        for card in cards:
            if card.members:
                members = json.loads(card.members) if isinstance(card.members, str) else card.members
                for m in members:
                    employees.add((m["employeeId"], m["employeeName"]))

        employee_list = [{"employeeId": eid, "employeeName": name} for eid, name in employees]
        return JsonResponse({"employees": employee_list}, safe=False)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def get_admin_emails():
    """
    Get emails of admin employees (primaryRole is 'SD-R-SA' or 'SD-R-A').
    """
    try:
        db = client[db_name]
        profiles = db['backend_diagnostics_profile']
        admin_roles = ['SD-R-SA', 'SD-R-A']
        admins = list(profiles.find(
            {'primaryRole': {'$in': admin_roles}},
            {'email': 1, '_id': 0}
        ))
        admin_emails = [admin['email'] for admin in admins if admin.get('email')]
        print(f"Fetched admin emails: {admin_emails}")  # Debug
        return admin_emails
    except Exception as e:
        print(f"Error fetching admin emails: {str(e)}")
        return []