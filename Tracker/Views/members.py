
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view

#permisiins disabled 
from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRoleAndDataPermission
from ..auth.permissions import SkipPermissionsIfDisabled
#Models
from ..models import Card
from ..models import Employee

@csrf_exempt
@api_view(['GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def get_all_employees(request):
    employees = Employee.objects.all().values('employeeId', 'employeeName')
    return JsonResponse(list(employees), safe=False)


@csrf_exempt
@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
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
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def get_board_members(request, board_id):
    if request.method == 'GET':
        # Get all unique members in the given board
        cards = Card.objects.filter(boardId=board_id)
        members_set = set()
        for card in cards:
            for member in card.members:
                members_set.add((member["employeeId"], member["employeeName"]))
        members_list = [{"employeeId": emp[0], "employeeName": emp[1]} for emp in members_set]
        return JsonResponse({"members": members_list}, safe=False)
    return JsonResponse({"error": "Invalid request method"}, status=400)



@csrf_exempt
@api_view(['GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
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

