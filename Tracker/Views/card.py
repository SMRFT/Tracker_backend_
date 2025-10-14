from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
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

logger = logging.getLogger(__name__)


@csrf_exempt
@api_view(['POST', 'GET', 'DELETE', 'PATCH'])
@permission_classes([HasRolePermission])
def CardCreateView(request, userRole, board_id, card_id=None):
    employee_id = request.data.get('auth-user-id')

    # Handle POST request
    if request.method == 'POST':
        # Add employeeId to the request data before serialization
        card_data = request.data.copy()
        card_data['employeeId'] = employee_id
        
        # Create serializer with context containing current employee ID
        serializer = CardSerializer(data=card_data, context={'current_employee_id': employee_id})
        print(f"Card View POST - employeeId being passed: {employee_id}")
        
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Card created successfully!'}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
   
    # Handle GET request
    elif request.method == 'GET':
        board_ID = board_id
        role = userRole

        # Check if the role is "Admin" and fetch all cards if true # Admin can view all cards # Filter by boardId if provided

        if role == "Admin":
            cards = Card.objects.all()

            if board_ID:
                cards = cards.filter(boardId=board_ID)

            # Separate filtering instead of UNION
            normal_cards = cards.exclude(columnId="done")

            last_week = now() - timedelta(days=7)
            done_cards = cards.filter(columnId="done", lastmodified_date__gte=last_week)

            # Combine in Python
            combined_cards = list(normal_cards) + list(done_cards)

            serializer = CardSerializer(combined_cards, many=True)
            return Response(serializer.data)

        else:
            if card_id:
                # Fetch specific card by cardId and boardId
                card = get_object_or_404(Card, cardId=card_id, boardId=board_ID)
                serializer = CardSerializer(card)
            else:
                # Fetch all cards for the specific boardId
                cards = Card.objects.filter(boardId=board_ID)

                        # Filter by employee ID if provided
            if employee_id:
                # Collect cards belonging to employee
                employee_cards = []
                for card in cards:
                    members = card.members or []  # assume list of dicts
                    if any(m.get('employeeId') == employee_id for m in members) or card.employeeId == employee_id:
                        employee_cards.append(card)

                # Separate filtering
                not_done = [c for c in employee_cards if c.columnId != "done"]
                last_week = now() - timedelta(days=7)
                recent_done = [c for c in employee_cards if c.columnId == "done" and c.lastmodified_date and c.lastmodified_date >= last_week]

                combined = not_done + recent_done

                serializer = CardSerializer(combined, many=True)
                return Response(serializer.data)
            else:
                return Response({"error": "employee_id is required"}, status=400)

    # Handle DELETE request with employee ID check
    elif request.method == 'DELETE':
        if not employee_id:
            return Response({'error': 'Employee ID is required'}, status=status.HTTP_400_BAD_REQUEST)

        card = get_object_or_404(Card, cardId=card_id)

        # Check if the employee ID matches the card owner's employee ID
        if card.employeeId != employee_id:
            return Response({'error': 'Permission denied: You are not authorized to delete this card.'}, status=status.HTTP_403_FORBIDDEN)

        # Proceed to delete the card if the employee ID matches
        card.delete()
        return Response({'message': 'Card deleted successfully!'}, status=status.HTTP_200_OK)

    # Handle PATCH request with employee ID check
    elif request.method == 'PATCH':
        card = get_object_or_404(Card, cardId=card_id)
        
        # Prepare updated data
        card_data = request.data.copy()
        card_data['employeeId'] = employee_id
        
        # Update using serializer with context containing current employee ID
        serializer = CardSerializer(
            card, 
            data=card_data, 
            partial=True, 
            context={'current_employee_id': employee_id}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Card updated successfully!'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


@csrf_exempt
@api_view(['DELETE'])
@permission_classes([ HasRolePermission])
class CardDetail(APIView):
    def delete(self, request, pk, format=None):
        try:
            card = Card.objects.get(pk=pk)
            card.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Card.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        

@csrf_exempt
@api_view(['POST', 'GET', 'DELETE', 'PATCH'])
@permission_classes([HasRolePermission])
def get_employee_cards(request, employee_id, board_id):
    print("API hit ✅ method:", request.method, "employee_id:", employee_id, "board_id:", board_id)

    if request.method == "GET":
        try:
            print("Inside GET handler ✅")

            # Get cards where the employeeId directly matches and boardId is the same
            direct_cards = Card.objects.filter(employeeId=str(employee_id), boardId=board_id)
            print("Direct cards queryset:", direct_cards)

            # Get cards where employee appears in the 'members' JSON field
            additional_cards = []
            for card in Card.objects.filter(boardId=board_id):
                print("Checking card:", card.cardId)
                members_field = card.members

                # Convert string to list if needed
                if isinstance(members_field, str):
                    try:
                        members_list = json.loads(members_field)
                    except json.JSONDecodeError:
                        members_list = []
                elif isinstance(members_field, list):
                    members_list = members_field
                else:
                    members_list = []

                print("Members parsed:", members_list)

                if any(str(member.get("employeeId")) == str(employee_id) for member in members_list):
                    print("✅ Found match in card:", card.cardId)
                    additional_cards.append(card)

            # Combine results and remove duplicates
            unique_cards = {}
            for card in list(direct_cards) + additional_cards:
                unique_cards[card.cardId] = {
                    "cardId": card.cardId,
                    "cardName": card.cardName,
                    "boardId": card.boardId,
                    "boardName": card.boardName,
                }

            return JsonResponse({"cards": list(unique_cards.values())}, safe=False)

        except Exception as e:
            import traceback
            print("❌ Error in GET handler:", str(e))
            print(traceback.format_exc())
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=400)

from django.http import JsonResponse
from rest_framework.decorators import api_view
from rest_framework import status
from datetime import datetime
from django.utils import timezone
from django.db import models
from ..models import Card
from ..serializers import CardSerializer
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
def GetOverdueCardsView(request, role):
    employee_id = request.query_params.get('auth-user-id')
    print(f"GetOverdueCardsView - employeeId: {employee_id}, role: {role}")

    if not employee_id:
        return JsonResponse({'error': 'Employee ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        now = timezone.now()  # timezone-aware

        # Base query: overdue but not in 'done'
        query = Card.objects.filter(
            enddate__lt=now
        ).exclude(
            columnId="done"
        )

        # If not Admin, restrict to employee and their members
        if role != "Admin":
            query = query.filter(
                models.Q(employeeId=employee_id) |
                models.Q(members__icontains=employee_id)  # since members is a JSON string
            )

        cards = query.all()
        serializer = CardSerializer(cards, many=True)

        # Add is_overdue flag
        data = []
        for card in serializer.data:
            card['is_overdue'] = True
            data.append(card)

        return JsonResponse(data, safe=False, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error in GetOverdueCardsView: {str(e)}")
        return JsonResponse({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_done_cards_by_date(request):
    role = request.query_params.get('role')
    employee_id = request.query_params.get('auth-user-id')
    from_date = request.query_params.get('from')
    to_date = request.query_params.get('to')

    if not from_date or not to_date:
        return Response(
            {"success": False, "error": "from and to dates are required"},
            status=400
        )

    try:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
        to_dt = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
        from_dt = timezone.make_aware(from_dt, timezone.get_current_timezone())
        to_dt = timezone.make_aware(to_dt, timezone.get_current_timezone())

        # Filter cards marked as "done" within the range
        cards = Card.objects.filter(
            columnId="done",
            enddate__range=[from_dt, to_dt]
        )

        # Filter by employee if not Admin
        if role != "Admin" and employee_id:
            cards = cards.filter(
                models.Q(employeeId=employee_id) | 
                models.Q(members__icontains=employee_id)  # Assuming members is a JSON field
            )

        serializer = CardSerializer(cards, many=True)
        return Response({"success": True, "data": serializer.data})

    except Exception as e:
        return Response(
            {"success": False, "error": str(e)},
            status=500
        )
