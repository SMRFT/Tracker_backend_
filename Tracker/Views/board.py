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

mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME", 'Tracker')

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri)


# Initialize logging

logger = logging.getLogger(__name__)


@api_view(['GET', 'POST', 'PUT'])
@permission_classes([HasRolePermission])
def BoardsView(request, boardId=None):
    db = client[db_name]          
    fs = gridfs.GridFS(db)
    collection = db['board']
    
    card_collection = db['card']

    # Extract employeeId from headers (for GET) or data (for POST/PUT)
    employeeId = (
        request.data.get('auth-user-id')
        if request.method != 'GET'
        else request.headers.get('auth-user-id')
    )
    print(f"View {request.method} - employeeId being passed: {employeeId}")
    
    if not employeeId:
        return Response({'error': 'Authentication data missing.'}, status=status.HTTP_401_UNAUTHORIZED)

    if request.method == 'GET':
        boards = list(collection.find({'employeeId': employeeId}))
        for board in boards:
            board['_id'] = str(board['_id'])
        return Response(boards, status=status.HTTP_200_OK)

    elif request.method == 'POST':
        board_data = request.data.copy()
        board_data['employeeId'] = employeeId

        serializer = BoardSerializer(data=board_data, context={'current_employee_id': employeeId})
        if serializer.is_valid():
            board_instance = serializer.save()
            mongodb_data = {
                'boardId': board_instance.boardId,
                'boardName': board_instance.boardName,
                'boardColor': board_instance.boardColor,
                'employeeId': board_instance.employeeId,
                'created_by': board_instance.created_by,
                'created_date': board_instance.created_date,
                'lastmodified_by': board_instance.lastmodified_by,
                'lastmodified_date': board_instance.lastmodified_date,
                'is_active': board_instance.is_active
            }
            # collection.insert_one(mongodb_data)
            return Response({'message': 'Board created successfully!'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'PUT':
        if boardId is None:
            return Response(
                {'error': 'Board ID is required to update a board.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            board_instance = Board.objects.get(boardId=boardId)
        except Board.DoesNotExist:
            return Response(
                {'error': 'Board not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if board_instance.employeeId != employeeId:
            return Response(
                {'error': 'Unauthorized to edit this board.'},
                status=status.HTTP_403_FORBIDDEN
            )

        board_data = request.data.copy()
        board_data['employeeId'] = employeeId

        serializer = BoardSerializer(
            board_instance,
            data=board_data,
            partial=True,
            context={'current_employee_id': employeeId}
        )

        if serializer.is_valid():
            updated_board = serializer.save()

            # 🔴 UPDATE BOARD IN MONGODB
            mongodb_update_data = {
                'boardName': updated_board.boardName,
                'boardColor': updated_board.boardColor,
                'employeeId': updated_board.employeeId,
                'lastmodified_by': updated_board.lastmodified_by,
                'lastmodified_date': updated_board.lastmodified_date,
                'is_active': updated_board.is_active
            }

            collection.update_one(
                {'boardId': boardId},
                {'$set': mongodb_update_data}
            )

            # 🔴 IMPORTANT: DEACTIVATE ALL CARDS IN MONGODB
            if updated_board.is_active is False:
                card_collection.update_many(
                    {
                        'boardId': boardId,
                        'is_active': True
                    },
                    {
                        '$set': {
                            'is_active': False,
                            'lastmodified_by': employeeId,
                            'lastmodified_date': updated_board.lastmodified_date
                        }
                    }
                )

            return Response(
                {'message': 'Board updated successfully!'},
                status=status.HTTP_200_OK
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


global_db_name=os.environ.get("GLOBAL_DB_NAME", "Global")
db = client[global_db_name]
profiles = db["backend_diagnostics_profile"]

def get_employee_name_by_id(employee_id):
    """
    Fetch employeeName from MongoDB 'backend_diagnostics_profile'
    using employeeId (supports both string and numeric types).
    """
    if not employee_id:
        return None
    try:
        # Try both string and int matches
        query = {
            "$or": [
                {"employeeId": str(employee_id)},
                {"employeeId": int(employee_id) if str(employee_id).isdigit() else None}
            ]
        }

        # Remove None from query
        query["$or"] = [cond for cond in query["$or"] if cond]

        profile = profiles.find_one(query, {"employeeName": 1, "_id": 0})

        return profile.get("employeeName") if profile else None
    except Exception as e:
        print(f"[ERROR] get_employee_name_by_id failed: {e}")
        return None

@api_view(['GET'])
@permission_classes([HasRolePermission])
def GetBoardsView(request, role):
    db = client[db_name]    
    board_collection = db['board']
    card_collection = db['card']
    employee_id = request.data.get('auth-user-id')
    employee_role = role

    print(f"GetBoardsView - employeeId: {employee_id}, role: {employee_role}")

    if not employee_id:
        return JsonResponse({'error': 'Employee ID is required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    if not employee_role:
        return JsonResponse({'error': 'Employee role is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        if employee_role == "Admin":
            # Get all active boards
            boards_cursor = board_collection.find({"is_active": True})
            boards = list(boards_cursor)

        elif employee_role == "HOD":
            # Boards created by HOD that are active
            boards_created_by_hod = list(board_collection.find({
                "employeeId": employee_id, 
                "is_active": True
            }))
            
            # Cards where HOD is member or creator
            cards_where_hod_is_member = list(card_collection.find({
                "$or": [
                    {"employeeId": employee_id},
                    {"members": {"$regex": f'"employeeId": "{employee_id}"'}}
                ]
            }))
            
            # Get board IDs from cards
            board_ids_from_cards = [card["boardId"] for card in cards_where_hod_is_member]
            
            # Boards associated with HOD through cards (and are active)
            boards_associated_with_hod = list(board_collection.find({
                "boardId": {"$in": board_ids_from_cards}, 
                "is_active": True
            }))
            
            # Combine and remove duplicates
            all_boards = {}
            for board in boards_created_by_hod + boards_associated_with_hod:
                all_boards[board["boardId"]] = board
            
            boards = list(all_boards.values())

        elif employee_role == "Employee":
            # Cards where Employee is member or creator
            cards_where_employee_is_member = list(card_collection.find({
                "$or": [
                    {"employeeId": employee_id},
                    {"members": {"$regex": f'"employeeId": "{employee_id}"'}}
                ]
            }))
            
            # Get board IDs from cards
            board_ids_from_cards = [card["boardId"] for card in cards_where_employee_is_member]
            
            # Boards where Employee is member through cards (and are active)
            boards_where_employee_is_member = list(board_collection.find({
                "boardId": {"$in": board_ids_from_cards}, 
                "is_active": True
            }))
            
            boards = boards_where_employee_is_member

        else:
            return JsonResponse({'error': 'Invalid role.'}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Add created_by_name and convert fields
        for board in boards:
            if '_id' in board:
                board['_id'] = str(board['_id'])
            if 'created_date' in board and board['created_date']:
                board['created_date'] = board['created_date'].isoformat()
            if 'lastmodified_date' in board and board['lastmodified_date']:
                board['lastmodified_date'] = board['lastmodified_date'].isoformat()

            # 🟢 Add creator name from profile collection
            created_by = board.get("created_by")
            board["created_by_name"] = get_employee_name_by_id(created_by)

        return JsonResponse(boards, safe=False, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in GetBoardsView: {str(e)}")
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
