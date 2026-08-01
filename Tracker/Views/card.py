from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRolePermission
from ..models import Card
from ..serializers import CardSerializer
from django.db import models
import logging
from datetime import timedelta
from django.utils import timezone
from django.utils.timezone import now
from dotenv import load_dotenv
import os
from pymongo import MongoClient
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from .email_utils import send_card_notification_email
logger = logging.getLogger(__name__)
from ..utils.db import get_tracker_db, get_global_db
from ..utils.employees import get_employee_names_by_ids
from ..utils.dates import normalize_date
from ..utils.members import parse_members, is_employee_in_members

def get_active_cards(board_id=None):
    """
    Safely query active cards directly from MongoDB to bypass
    Djongo's SQLDecodeError on naked boolean fields.
    """
    db = get_tracker_db()
    card_collection = db["card"]
    
    query = {"is_active": True}
    if board_id is not None:
        query["boardId"] = int(board_id) if str(board_id).isdigit() else board_id
        
    cards_data = list(card_collection.find(query))
    cards = []
    for c_data in cards_data:
        data_copy = c_data.copy()
        if "_id" in data_copy:
            del data_copy["_id"]
            
        # Coerce datetime fields to dates for serialization compatibility
        for field in ["startdate", "enddate"]:
            val = data_copy.get(field)
            if isinstance(val, datetime):
                data_copy[field] = val.date()
            elif isinstance(val, str) and val:
                try:
                    data_copy[field] = datetime.strptime(val, "%Y-%m-%d").date()
                except Exception:
                    pass

        # Ensure DateTimeFields are timezone-aware to match Django settings
        for field in ["created_date", "lastmodified_date", "last_mail_sent_date"]:
            val = data_copy.get(field)
            if isinstance(val, datetime):
                data_copy[field] = normalize_date(val)

        p_val = data_copy.get("priority")
        if not p_val or p_val == "None" or p_val == "null":
            data_copy["priority"] = "Low"
        if "viewed_by" not in data_copy or data_copy["viewed_by"] is None:
            data_copy["viewed_by"] = []

        cards.append(Card(**data_copy))
    return cards



@csrf_exempt
@api_view(['POST', 'GET', 'DELETE', 'PATCH'])
@permission_classes([HasRolePermission])
def CardCreateView(request, userRole, board_id, card_id=None):
    employee_id = request.data.get('auth-user-id')
    db_global = get_global_db()
    profiles = db_global["backend_diagnostics_profile"]

    # Handle POST request
    if request.method == 'POST':
        # Add employeeId to the request data before serialization
        card_data = request.data.copy()
        card_data['employeeId'] = employee_id
        
        # Create serializer with context containing current employee ID
        serializer = CardSerializer(data=card_data, context={'current_employee_id': employee_id})
        logger.debug(f"Card View POST - employeeId being passed: {employee_id}")
        
        if serializer.is_valid():
            card = serializer.save()
            
            # Send email to members
            members = parse_members(card.members)

            if members:
                logger.debug(f"Triggering creation notification for {len(members)} members")
                send_card_notification_email(card, members, profiles, action_type="assigned")
                
            return Response({'message': 'Card created successfully!'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
   
    # Handle GET request
    elif request.method == 'GET':
        board_ID = board_id
        allowed_actions = request.data.get('auth-allowed-action-codes', [])
        is_admin = "ST-R-A" in allowed_actions
        role = "Admin" if is_admin else "Employee"

        if role == "Admin":
            if board_ID:
                cards_active = get_active_cards(board_ID)
            else:
                cards_active = get_active_cards()

            # Filter for done vs others
            last_week = now() - timedelta(days=7)

            normal_cards = [c for c in cards_active if c.columnId != "done"]
            done_cards = [
                c for c in cards_active
                if c.columnId == "done" and c.lastmodified_date and c.lastmodified_date >= last_week
            ]

            combined_cards = normal_cards + done_cards

            serializer = CardSerializer(combined_cards, many=True)
            data = serializer.data

            # Bulk fetch employee names to avoid N+1 queries
            all_emp_ids = {str(c.get("created_by")) for c in data if c.get("created_by")} | \
                          {str(c.get("lastmodified_by")) for c in data if c.get("lastmodified_by")}
            if all_emp_ids:
                employee_profiles = list(profiles.find(
                    {"employeeId": {"$in": list(all_emp_ids)}},
                    {"employeeId": 1, "employeeName": 1, "_id": 0}
                ))
                name_map = {p["employeeId"]: p["employeeName"] for p in employee_profiles}
            else:
                name_map = {}

            for card_data in data:
                created_by = card_data.get("created_by")
                lastmodified_by = card_data.get("lastmodified_by")
                card_data["created_by_name"] = name_map.get(str(created_by)) if created_by else None
                card_data["lastmodified_by_name"] = name_map.get(str(lastmodified_by)) if lastmodified_by else None

            return Response(data)
                    
        else:
            if card_id:
                card = get_object_or_404(Card, cardId=card_id, boardId=board_ID)

                if not (card.is_active == True or card.is_active == 1):
                    return Response({"error": "Card not found"}, status=404)

                serializer = CardSerializer(card)
                return Response(serializer.data)

            else:
                # Djongo safe filtering
                cards = get_active_cards(board_ID)

            if employee_id:
                employee_cards = []

                for card in cards:
                    members = parse_members(card.members)

                    if (
                        any(m.get("employeeId") == employee_id for m in members)
                        or card.employeeId == employee_id
                    ):
                        employee_cards.append(card)

                not_done = [c for c in employee_cards if c.columnId != "done"]

                last_week = now() - timedelta(days=7)

                recent_done = [
                    c for c in employee_cards
                    if c.columnId == "done"
                    and c.lastmodified_date
                    and c.lastmodified_date >= last_week
                ]

                combined = not_done + recent_done

                serializer = CardSerializer(combined, many=True)
                data = serializer.data

                # Bulk fetch employee names to avoid N+1 queries
                all_emp_ids = {str(c.get("created_by")) for c in data if c.get("created_by")} | \
                              {str(c.get("lastmodified_by")) for c in data if c.get("lastmodified_by")}
                if all_emp_ids:
                    employee_profiles = list(profiles.find(
                        {"employeeId": {"$in": list(all_emp_ids)}},
                        {"employeeId": 1, "employeeName": 1, "_id": 0}
                    ))
                    name_map = {p["employeeId"]: p["employeeName"] for p in employee_profiles}
                else:
                    name_map = {}

                for card_data in data:
                    created_by = card_data.get("created_by")
                    lastmodified_by = card_data.get("lastmodified_by")
                    card_data["created_by_name"] = name_map.get(str(created_by)) if created_by else None
                    card_data["lastmodified_by_name"] = name_map.get(str(lastmodified_by)) if lastmodified_by else None

                return Response(data)
    # Handle DELETE request with employee ID check
    elif request.method == 'DELETE':
        if not employee_id:
            return Response({'error': 'Employee ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        card = get_object_or_404(Card, cardId=card_id)

        # Check if the employee ID matches the card owner's employee ID
        if card.employeeId != employee_id:
            return Response({'error': 'Permission denied: You are not authorized to delete this card.'}, status=status.HTTP_403_FORBIDDEN)

        # Proceed to soft delete the card if the employee ID matches
        card.lastmodified_by = employee_id
        card.lastmodified_date = timezone.now()   # <-- correct
        card.is_active = False
        card.save()
        return Response({'message': 'Card deleted successfully!'}, status=status.HTTP_200_OK)

    # Handle PATCH request with employee ID check
    elif request.method == 'PATCH':
        card = get_object_or_404(Card, cardId=card_id)
        card_data = request.data.copy()

        # Enforce column update restrictions
        if 'columnId' in card_data and card_data['columnId'] != card.columnId:
            new_column = card_data['columnId']
            if new_column in ['do', 'doing', 'done', 'hold']:
                is_creator = str(card.employeeId) == str(employee_id)
                members_list = parse_members(card.members)
                is_member = any(str(m.get('employeeId')) == str(employee_id) for m in members_list)
                
                if not (is_creator or is_member):
                    return Response(
                        {'error': 'Permission denied: Only the card creator or assigned members can change the card status.'}, 
                        status=status.HTTP_403_FORBIDDEN
                    )

        # Get existing members to detect additions
        old_members = parse_members(card.members)
        old_member_ids = {str(m.get('employeeId')) for m in old_members if m.get('employeeId')}

        # Update using serializer with context containing current employee ID
        serializer = CardSerializer(
            card, 
            data=card_data, 
            partial=True, 
            context={'current_employee_id': employee_id}
        )
        
        if serializer.is_valid():
            updated_card = serializer.save()
            
            # Detect newly added members
            new_members = parse_members(updated_card.members)

            new_member_ids = {str(m.get('employeeId')) for m in new_members if m.get('employeeId')}
            
            added_members = [m for m in new_members if str(m.get('employeeId')) not in old_member_ids]
            removed_members = [m for m in old_members if str(m.get('employeeId')) not in new_member_ids]
            
            logger.debug(f"Patch detected {len(added_members)} new members added and {len(removed_members)} members removed")
            
            if added_members:
                send_card_notification_email(updated_card, added_members, profiles, action_type="added")
            
            if removed_members:
                send_card_notification_email(updated_card, removed_members, profiles, action_type="removed")
                
            return Response({'message': 'Card updated successfully!'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
@api_view(["GET"])
@permission_classes([HasRolePermission])
def get_inactive_cards(request):
    # Step 1: Load ALL cards (Djongo-friendly)
    all_cards = list(Card.objects.all())

    # Step 2: Python-side filter (bypasses Djongo SQL)
    inactive_cards = [
        c for c in all_cards
        if c.is_active in [False, 0, "false", "False", None]
    ]

    allowed_actions = request.data.get('auth-allowed-action-codes', [])
    is_admin = "ST-R-A" in allowed_actions
    employee_id = request.data.get('auth-user-id')

    if not is_admin and employee_id:
        inactive_cards = [
            c for c in inactive_cards
            if str(c.employeeId) == str(employee_id)
            or is_employee_in_members(c.members, employee_id)
        ]

    # Filter by from and to dates if provided
    from_date_str = request.query_params.get('from')
    to_date_str = request.query_params.get('to')

    if from_date_str and to_date_str:
        try:
            from_dt = timezone.make_aware(
                datetime.strptime(from_date_str, "%Y-%m-%d").replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            )
            to_dt = timezone.make_aware(
                datetime.strptime(to_date_str, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
            )
            
            filtered_cards = []
            for c in inactive_cards:
                lmd = c.lastmodified_date
                if lmd:
                    lmd_norm = normalize_date(lmd)
                    if lmd_norm and from_dt <= lmd_norm <= to_dt:
                        filtered_cards.append(c)
            inactive_cards = filtered_cards
        except Exception as e:
            logger.error(f"Error parsing dates in get_inactive_cards: {str(e)}")

    # Step 3: Serialize
    serializer = CardSerializer(inactive_cards, many=True)
    data = serializer.data

    # Step 4: Add employee names (batch-resolved in one query instead of one per card)
    referenced_ids = set()
    for card in data:
        referenced_ids.add(card.get("created_by"))
        referenced_ids.add(card.get("lastmodified_by"))
    names_by_id = get_employee_names_by_ids(referenced_ids)

    for card in data:
        created_by = card.get("created_by")
        lastmodified_by = card.get("lastmodified_by")

        card["created_by_name"] = names_by_id.get(str(created_by)) if created_by else None
        card["lastmodified_by_name"] = names_by_id.get(str(lastmodified_by)) if lastmodified_by else None

    return Response(data, status=status.HTTP_200_OK)

@csrf_exempt
@api_view(['POST', 'GET', 'DELETE', 'PATCH'])
@permission_classes([HasRolePermission])
def get_employee_cards(request, employee_id, board_id):
    # print("API hit ✅ method:", request.method, "employee_id:", employee_id, "board_id:", board_id)
    
    allowed_actions = request.data.get('auth-allowed-action-codes', [])
    is_admin_or_hod = "ST-R-A" in allowed_actions or "ST-R-HOD" in allowed_actions
    authenticated_id = request.data.get('auth-user-id')

    if not is_admin_or_hod:
        if str(employee_id) != str(authenticated_id):
            return JsonResponse(
                {"error": "Unauthorized to view other users' cards."},
                status=status.HTTP_403_FORBIDDEN
            )

    if request.method == "GET":
        try:
            # print("Inside GET handler ✅")

            # Get cards where the employeeId directly matches and boardId is the same
            direct_cards = Card.objects.filter(employeeId=str(employee_id), boardId=board_id)
            # print("Direct cards queryset:", direct_cards)

            # Get cards where employee appears in the 'members' JSON field
            additional_cards = [
                card for card in Card.objects.filter(boardId=board_id)
                if is_employee_in_members(card.members, employee_id)
            ]

            # Combine results and remove duplicates
            unique_cards = {}
            for card in list(direct_cards) + additional_cards:
                unique_cards[card.cardId] = {
                    "cardId": card.cardId,
                    "cardName": card.cardName,
                    "boardId": card.boardId,
                    "boardName": card.boardName,
                    "columnId":card.columnId,
                    "created_date":card.created_date,
                    "lastmodified_date":card.lastmodified_date,
                }

            return JsonResponse({"cards": list(unique_cards.values())}, safe=False)

        except Exception as e:
            import traceback
            # print("❌ Error in GET handler:", str(e))
            # print(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=400)

def is_card_active(card):
    return getattr(card, "is_active", False) is True

@api_view(['GET'])
@permission_classes([HasRolePermission])
def GetOverdueCardsView(request, role):
    allowed_actions = request.data.get('auth-allowed-action-codes', [])
    is_admin = "ST-R-A" in allowed_actions
    authenticated_id = request.data.get('auth-user-id')

    employee_id = request.query_params.get('auth-user-id')
    if not is_admin:
        employee_id = authenticated_id

    if not employee_id:
        return JsonResponse(
            {'error': 'Employee ID is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        now = timezone.now()

        # ⚠️ DB filter is NOT reliable for Mongo
        cards = Card.objects.filter(
            enddate__lt=now
        ).exclude(
            columnId="done"
        )

        cards = cards.all()

        # ✅ HARD FILTER (Python level)
        cards = [
            card for card in cards
            if is_card_active(card)
        ]

        # ✅ Role-based filter
        if not is_admin:
            cards = [
                card for card in cards
                if str(card.employeeId) == str(employee_id)
                or is_employee_in_members(card.members, employee_id)
            ]

        serializer = CardSerializer(cards, many=True)

        data = []
        for card in serializer.data:
            card["is_overdue"] = True
            data.append(card)

        return JsonResponse(data, safe=False, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in GetOverdueCardsView: {str(e)}")
        return JsonResponse(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_done_cards_by_date(request):
    allowed_actions = request.data.get('auth-allowed-action-codes', [])
    is_admin = "ST-R-A" in allowed_actions
    authenticated_id = request.data.get('auth-user-id')

    employee_id = request.query_params.get('auth-user-id')
    if not is_admin:
        employee_id = authenticated_id

    from_date = request.query_params.get('from')
    to_date = request.query_params.get('to')

    if not from_date or not to_date:
        return Response(
            {"success": False, "error": "from and to dates are required"},
            status=400
        )

    try:
        from_dt = timezone.make_aware(
            datetime.strptime(from_date, "%Y-%m-%d").replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        )
        to_dt = timezone.make_aware(
            datetime.strptime(to_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
        )

        cards = Card.objects.filter(
            columnId="done",
            enddate__range=[from_dt, to_dt]
        ).all()

        # ✅ HARD FILTER
        cards = [
            card for card in cards
            if is_card_active(card)
        ]

        # ✅ Role filter
        if not is_admin and employee_id:
            cards = [
                card for card in cards
                if str(card.employeeId) == str(employee_id)
                or is_employee_in_members(card.members, employee_id)
            ]

        serializer = CardSerializer(cards, many=True)

        return Response({
            "success": True,
            "data": serializer.data
        })

    except Exception as e:
        return Response(
            {"success": False, "error": str(e)},
            status=500
        )

@csrf_exempt
@api_view(['POST'])
@permission_classes([HasRolePermission])
def restore_card(request, card_id):
    from ..utils.auth import get_auth_user_id
    employee_id = get_auth_user_id(request)
    if not employee_id:
        return Response({'error': 'Employee ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
    card = get_object_or_404(Card, cardId=card_id)
    
    # Allow restore for admin, HOD, or the card owner
    allowed_actions = request.data.get('auth-allowed-action-codes', [])
    is_admin_or_hod = "ST-R-A" in allowed_actions or "ST-R-HOD" in allowed_actions
    
    if not is_admin_or_hod and str(card.employeeId) != str(employee_id):
        return Response({'error': 'Permission denied: You are not authorized to restore this card.'}, status=status.HTTP_403_FORBIDDEN)
        
    card.is_active = True
    card.lastmodified_by = employee_id
    card.lastmodified_date = timezone.now()
    card.save()
    return Response({'message': 'Card restored successfully!'}, status=status.HTTP_200_OK)

@csrf_exempt
@api_view(['POST'])
@permission_classes([HasRolePermission])
def mark_card_viewed(request, card_id):
    from ..utils.auth import get_auth_user_id
    employee_id = get_auth_user_id(request)
    if not employee_id:
        return Response({'error': 'Employee ID is required'}, status=status.HTTP_400_BAD_REQUEST)

    card = Card.objects.filter(cardId=card_id).first()
    if not card:
        return Response({'error': 'Card not found'}, status=status.HTTP_404_NOT_FOUND)

    viewed_by = card.viewed_by if isinstance(card.viewed_by, list) else []
    emp_str = str(employee_id)
    if emp_str not in viewed_by:
        viewed_by.append(emp_str)
        card.viewed_by = viewed_by
        card.save()

    return Response({'message': 'Card marked as viewed', 'viewed_by': card.viewed_by}, status=status.HTTP_200_OK)

