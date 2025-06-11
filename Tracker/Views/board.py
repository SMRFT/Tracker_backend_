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
from ..serializers import BoardSerializer
from ..models import Board, Card
from pyauth.auth import HasRolePermission
from dotenv import load_dotenv
load_dotenv()  # Load from .env if present

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("TRACKER_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME")

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri, tls=True,tlsAllowInvalidCertificates=True,tlsCAFile=certifi.where())


# Initialize logging

logger = logging.getLogger(__name__)

@csrf_exempt
@api_view(['POST', 'PUT', 'DELETE'])
@permission_classes([HasRolePermission])
def BoardsView(request,name, boardId=None):
    db = client[db_name]          
    fs = gridfs.GridFS(db)
    collection = db['Tracker_board']
    
    # Extract employeeId and employeeName from request headers
    employeeId = request.data.get('auth-user-id')
    employeeName = name
    
    # Validate that required authentication data is present
    if not employeeId or not employeeName:
        return Response({'error': 'Authentication data missing.'}, status=status.HTTP_401_UNAUTHORIZED)
    
    if request.method == 'POST':
        # Add employeeId and employeeName to the request data before serialization
        board_data = request.data.copy()
        board_data['employeeId'] = employeeId
        board_data['employeeName'] = employeeName
        
        serializer = BoardSerializer(data=board_data)
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Board created successfully!'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
    elif request.method == 'PUT':
        if boardId is None:
            return Response({'error': 'Board ID is required to update a board.'}, status=status.HTTP_400_BAD_REQUEST)
            
        board = collection.find_one({'boardId': boardId})
        if not board:
            return Response({'error': 'Board not found.'}, status=status.HTTP_404_NOT_FOUND)
            
        # Use employeeId from headers for authorization check
        if board['employeeId'] != employeeId:
            return Response({'error': 'Unauthorized to edit this board.'}, status=status.HTTP_403_FORBIDDEN)
            
        updated_data = {
            'boardName': request.data.get('boardName', board['boardName']),
            'boardColor': request.data.get('boardColor', board['boardColor']),
            'employeeId': employeeId,  # Use from headers
            'employeeName': employeeName,  # Use from headers
        }
        
        result = collection.update_one(
            {'boardId': boardId}, {'$set': updated_data})
            
        if result.modified_count > 0:
            return Response({'message': 'Board updated successfully!'}, status=status.HTTP_200_OK)
        else:
            return Response({'message': 'No changes made to the board.'}, status=status.HTTP_200_OK)
            
    elif request.method == 'DELETE':
        if boardId is None:
            return Response({'error': 'Board ID is required to delete a board.'}, status=status.HTTP_400_BAD_REQUEST)
            
        board = collection.find_one({'boardId': boardId})
        if not board:
            return Response({'error': 'Board not found.'}, status=status.HTTP_404_NOT_FOUND)
            
        # Use employeeId from headers for authorization check
        if board['employeeId'] != employeeId:
            return Response({'error': 'Unauthorized to delete this board.'}, status=status.HTTP_403_FORBIDDEN)
            
        result = collection.delete_one({'boardId': boardId})
        if result.deleted_count > 0:
            return Response({'message': 'Board deleted successfully!'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Board could not be deleted.'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([HasRolePermission])
def GetBoardsView(request, role):  # Add 'role' parameter here
    # Extract employee data from headers
    employee_id = request.data.get('auth-user-id')
    employee_role = role  # Use the role from URL parameter
    
    if not employee_id:
        return JsonResponse({'error': 'Employee ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not employee_role:
        return JsonResponse({'error': 'Employee role is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if employee_role == "Admin":
            boards = Board.objects.all()            
             
        elif employee_role == "HOD":
            boards_created_by_hod = Board.objects.filter(employeeId=employee_id)
            cards_where_hod_is_member = [
                card for card in Card.objects.all()
                if any(member.get('employeeId') == employee_id for member in card.members or [])
                or card.employeeId == employee_id
            ]
            board_ids_from_cards = set(card.boardId for card in cards_where_hod_is_member)
            boards_associated_with_hod = Board.objects.filter(boardId__in=board_ids_from_cards)
            boards = (boards_created_by_hod | boards_associated_with_hod).distinct()

        elif employee_role == "Employee":
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
        return JsonResponse(serializer.data, safe=False, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in GetBoardsView: {str(e)}")
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)