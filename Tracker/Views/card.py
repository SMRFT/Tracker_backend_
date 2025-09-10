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

        # Check if the role is "Admin" and fetch all cards if true
        if role == "Admin":
            cards = Card.objects.all()  # Admin can view all cards
            if board_ID:
                cards = cards.filter(boardId=board_ID)  # Filter by boardId if provided
            serializer = CardSerializer(cards, many=True)
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
                    filtered_cards = []
                    for card in cards:
                        members = card.members  # Assume this is a list of dicts
                        if members and any(member['employeeId'] == employee_id for member in members):
                            filtered_cards.append(card)
                        elif card.employeeId == employee_id:
                            filtered_cards.append(card)

                    serializer = CardSerializer(filtered_cards, many=True)
                else:
                    serializer = CardSerializer(cards, many=True)

        return Response(serializer.data)

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



