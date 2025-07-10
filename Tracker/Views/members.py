import json
from pymongo import MongoClient
import os
import certifi
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRolePermission
from ..models import Card

from dotenv import load_dotenv

load_dotenv()  # Load from .env if present

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("GLOBAL_DB_NAME",'Global')
       

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri, tls=True,tlsAllowInvalidCertificates=True,tlsCAFile=certifi.where())

@csrf_exempt
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_all_employees(request):
    try:
        db = client[db_name]
        profile_collection = db['backend_diagnostics_profile']
        departments_collection = db['backend_diagnostics_Departments']
        designations_collection = db['backend_diagnostics_Designation']  # Adjust collection name as needed
        
        # Get all employees
        employees = list(profile_collection.find(
            {},
            {
                'employeeId': 1, 
                'employeeName': 1, 
                'department': 1, 
                'designation': 1, 
                '_id': 0
            }
        ))
        
        # Create lookup dictionaries for better performance
        departments_dict = {}
        for dept in departments_collection.find({'is_active': True}):
            departments_dict[dept['department_code']] = dept['department_name']
        
        designations_dict = {}
        for desig in designations_collection.find({'is_active': True}):
            designations_dict[desig['Designation_code']] = desig['designation']
        
        # Replace codes with names
        for employee in employees:
            employee['department'] = departments_dict.get(employee['department'], employee['department'])
            employee['designation'] = designations_dict.get(employee['designation'], employee['designation'])
        
        return JsonResponse(employees, safe=False)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@csrf_exempt
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([ HasRolePermission])
def add_member_to_card(request):
    card_id = request.data.get('cardId') or request.query_params.get('cardId')

    # Check if the card exists
    try:
        card = Card.objects.get(cardId=card_id)
    except Card.DoesNotExist:
        return Response({'error': 'Card not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Handle GET request (Fetch members)
    if request.method == 'GET':
        members = card.members if card.members else []
        return Response(members, status=status.HTTP_200_OK)

    # Handle POST request (Add a member)
    if request.method == 'POST':
        employee_id = request.data.get('employeeId')
        employee_name = request.data.get('employeeName')

        if card.members is None:
            card.members = []

        if any(member['employeeId'] == employee_id for member in card.members):
            return Response({'error': 'This member is already added to the card.'}, status=status.HTTP_400_BAD_REQUEST)

        card.members.append({
            'employeeId': employee_id,
            'employeeName': employee_name,
        })
        card.save()

        return Response({'message': 'Member added successfully!'}, status=status.HTTP_201_CREATED)

    # Handle DELETE request (Remove a member)
    if request.method == 'DELETE':
        employee_id = request.query_params.get('employeeId')

        if card.members is None or not any(member['employeeId'] == employee_id for member in card.members):
            return Response({'error': 'Member not found in the card.'}, status=status.HTTP_404_NOT_FOUND)

        # Remove the member from the list
        card.members = [
            member for member in card.members if member['employeeId'] != employee_id]
        card.save()

        return Response({'message': 'Member removed successfully!'}, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['GET'])
def get_board_employees(request, board_id):
    """
    Fetch employees from the `members` field of the `Card` model for a given board ID.
    """
    if request.method == "GET":
        try:
            # Get all cards that belong to the given boardId
            cards = Card.objects.filter(boardId=board_id)
            # Extract members from all matching cards
            employees = set()
            for card in cards:
                if card.members:  # Ensure members field is not empty
                    card_members = json.loads(card.members) if isinstance(card.members, str) else card.members
                    for member in card_members:
                        employees.add((member["employeeId"], member["employeeName"]))
            # Convert set to a list of dictionaries
            employee_list = [{"employeeId": emp_id, "employeeName": emp_name} for emp_id, emp_name in employees]
            return JsonResponse({"employees": employee_list}, safe=False)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)