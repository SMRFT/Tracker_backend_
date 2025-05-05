
from django.http import JsonResponse
from rest_framework.decorators import api_view , permission_classes
from rest_framework import status
import logging
from pymongo import MongoClient
import gridfs
from django.http import JsonResponse
from rest_framework.response import Response
import certifi
from django.views.decorators.csrf import csrf_exempt
import os


#permisiins disabled 
from ..auth.permissions import SkipPermissionsIfDisabled
# Models and Serializers
from ..serializers import BoardSerializer
from ..models import Employee
from ..models import Board, Card

from pyauth.auth import HasRoleAndDataPermission

from dotenv import load_dotenv

load_dotenv()  # Load from .env if present

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME")

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri, tls=True, tlsCAFile=certifi.where())


# Initialize logging

logger = logging.getLogger(__name__)

@csrf_exempt
@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def BoardsView(request, boardId=None):
    db = client[db_name]          
    fs = gridfs.GridFS(db)
    collection = db['Tracker_board']
    if request.method == 'POST':
        serializer = BoardSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Board created successfully!'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'PUT':
        if boardId is None:
            return JsonResponse({'error': 'Board ID is required to update a board.'}, status=400)
        board = collection.find_one({'boardId': boardId})
        if not board:
            return JsonResponse({'error': 'Board not found.'}, status=404)
        request_employee_id = request.data.get('employeeId')
        if board['employeeId'] != request_employee_id:
            return JsonResponse({'error': 'Unauthorized to edit this board.'}, status=403)
        updated_data = {
            'boardName': request.data.get('boardName', board['boardName']),
            'boardColor': request.data.get('boardColor', board['boardColor']),
            'employeeId': request_employee_id,
            'employeeName': request.data.get('employeeName', board['employeeName']),
        }
        result = collection.update_one(
            {'boardId': boardId}, {'$set': updated_data})
        if result.modified_count > 0:
            return JsonResponse({'message': 'Board updated successfully!'}, status=200)
        else:
            return JsonResponse({'message': 'No changes made to the board.'}, status=200)
    elif request.method == 'DELETE':
        if boardId is None:
            return JsonResponse({'error': 'Title is required to delete a board.'}, status=400)
        board = collection.find_one({'boardId': boardId})
        if not board:
            return JsonResponse({'error': 'Board not found.'}, status=404)
        request_employee_id = request.data.get('employeeId')
        if board['employeeId'] != request_employee_id:
            return JsonResponse({'error': 'Unauthorized to delete this board.'}, status=403)
        result = collection.delete_one({'boardId': boardId})
        if result.deleted_count > 0:
            return JsonResponse({'message': 'Board deleted successfully!'}, status=200)
        else:
            return JsonResponse({'error': 'Board could not be deleted.'}, status=400)



@api_view(['GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def GetBoardsView(request):
    employee_id = request.GET.get('employeeId')

    if not employee_id:
        return JsonResponse({'error': 'Employee ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        employee = Employee.objects.filter(employeeId=employee_id).first()
        if not employee:
            return JsonResponse({'error': 'Employee not found.'}, status=status.HTTP_404_NOT_FOUND)

        role = employee.role

        if role == "Admin":
            boards = Board.objects.all()            
             
        elif role == "HOD":
            boards_created_by_hod = Board.objects.filter(employeeId=employee_id)
            cards_where_hod_is_member = [
                card for card in Card.objects.all()
                if any(member.get('employeeId') == employee_id for member in card.members or [])
                or card.employeeId == employee_id
            ]
            board_ids_from_cards = set(card.boardId for card in cards_where_hod_is_member)
            boards_associated_with_hod = Board.objects.filter(boardId__in=board_ids_from_cards)
            boards = (boards_created_by_hod | boards_associated_with_hod).distinct()

        elif role == "Employee":
            boards_created_by_employee = Board.objects.filter(employeeId=employee_id)
            cards_where_employee_is_member = [
                card for card in Card.objects.all()
                if any(member.get('employeeId') == employee_id for member in card.members or [])
                or card.employeeId == employee_id
            ]
            board_ids_from_cards = set(card.boardId for card in cards_where_employee_is_member)
            boards_where_employee_is_member = Board.objects.filter(boardId__in=board_ids_from_cards)
            boards = (boards_created_by_employee | boards_where_employee_is_member).distinct()

        else:
            return JsonResponse({'error': 'Invalid role.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = BoardSerializer(boards, many=True)
        return JsonResponse(serializer.data,safe=False, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in GetBoardsView: {str(e)}")
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
