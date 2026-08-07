from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
import logging
from ..utils.db import get_tracker_db
from ..utils.employees import get_employee_names_by_ids
from ..utils.auth import get_auth_user_id, get_user_role
from ..utils.responses import api_success, api_error
from ..serializers import BoardSerializer
from ..models import Board
from pyauth.auth import HasRolePermission
from datetime import timedelta
from django.utils.timezone import now
from ..utils.dates import normalize_date

# Initialize logging
logger = logging.getLogger(__name__)

@api_view(['GET', 'POST', 'PUT'])
@permission_classes([HasRolePermission])
def BoardsView(request, boardId=None):
    db = get_tracker_db()          
    collection = db['board']
    card_collection = db['card']

    employeeId = get_auth_user_id(request)
    logger.debug(f"View {request.method} - employeeId being passed: {employeeId}")
    
    if not employeeId:
        return api_error('Authentication data missing.', code="UNAUTHORIZED", status_code=status.HTTP_401_UNAUTHORIZED)

    if request.method == 'GET':
        boards = list(collection.find({'employeeId': employeeId}))
        for board in boards:
            board['_id'] = str(board['_id'])
        return api_success(boards)

    elif request.method == 'POST':
        board_data = request.data.copy()
        board_data['employeeId'] = employeeId

        serializer = BoardSerializer(data=board_data, context={'current_employee_id': employeeId})
        if serializer.is_valid():
            board_instance = serializer.save()
            return api_success(
                message='Board created successfully!',
                status_code=status.HTTP_201_CREATED
            )
        return api_error('Validation failed', details=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'PUT':
        if boardId is None:
            return api_error('Board ID is required to update a board.', status_code=status.HTTP_400_BAD_REQUEST)

        board_instance = Board.objects.filter(boardId=boardId).first()
        if not board_instance:
            return api_error('Board not found.', code="NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND)

        employee_role = get_user_role(request)
        is_admin = (
            employee_role == "Admin" or
            request.data.get("userRole") == "Admin" or
            request.data.get("role") == "Admin"
        )
        is_owner = str(board_instance.employeeId) == str(employeeId) or str(board_instance.created_by) == str(employeeId)

        if not (is_admin or is_owner):
            return api_error('Unauthorized to edit or delete this board.', code="FORBIDDEN", status_code=status.HTTP_403_FORBIDDEN)

        board_data = request.data.copy()
        if not is_owner:
            board_data['employeeId'] = board_instance.employeeId
        else:
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

            return api_success(message='Board updated successfully!')

        return api_error('Validation failed', details=serializer.errors, status_code=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([HasRolePermission])
def GetBoardsView(request, role):
    db = get_tracker_db()    
    board_collection = db['board']
    card_collection = db['card']
    employee_id = get_auth_user_id(request)
    employee_role = get_user_role(request)

    logger.debug(f"GetBoardsView - employeeId: {employee_id}, role: {employee_role}")

    if not employee_id:
        return api_error('Employee ID is required.', status_code=status.HTTP_400_BAD_REQUEST)

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
                "is_active": True,
                "$or": [
                    {"employeeId": employee_id},
                    {"members": {"$regex": f'"employeeId": "{employee_id}"'}}
                ]
            }))
            
            last_week = now() - timedelta(days=7)
            valid_cards = []
            for c in cards_where_hod_is_member:
                if c.get("columnId") == "done":
                    lmd = c.get("lastmodified_date")
                    if lmd:
                        lmd_norm = normalize_date(lmd)
                        if lmd_norm and lmd_norm >= last_week:
                            valid_cards.append(c)
                else:
                    valid_cards.append(c)
            
            # Get board IDs from cards
            board_ids_from_cards = [card["boardId"] for card in valid_cards]
            
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
                "is_active": True,
                "$or": [
                    {"employeeId": employee_id},
                    {"members": {"$regex": f'"employeeId": "{employee_id}"'}}
                ]
            }))
            
            last_week = now() - timedelta(days=7)
            valid_cards = []
            for c in cards_where_employee_is_member:
                if c.get("columnId") == "done":
                    lmd = c.get("lastmodified_date")
                    if lmd:
                        lmd_norm = normalize_date(lmd)
                        if lmd_norm and lmd_norm >= last_week:
                            valid_cards.append(c)
                else:
                    valid_cards.append(c)
            
            # Get board IDs from cards
            board_ids_from_cards = [card["boardId"] for card in valid_cards]
            
            # Boards where Employee is member through cards (and are active)
            boards_where_employee_is_member = list(board_collection.find({
                "boardId": {"$in": board_ids_from_cards}, 
                "is_active": True
            }))
            
            boards = boards_where_employee_is_member

        else:
            return api_error('Invalid role.', status_code=status.HTTP_400_BAD_REQUEST)

        # Batch-resolve creator names in one query instead of one query per board
        names_by_id = get_employee_names_by_ids(board.get("created_by") for board in boards)

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
            board["created_by_name"] = names_by_id.get(str(created_by)) if created_by else None

        return api_success(boards)

    except Exception as e:
        logger.error(f"Error in GetBoardsView: {str(e)}")
        # Centralized exception handler handles this, but keeping log + api_error fallback
        return api_error(str(e), code="SERVER_ERROR", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
