from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from datetime import datetime
from rest_framework.views import APIView
from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRoleAndDataPermission
from ..auth.permissions import SkipPermissionsIfDisabled
from ..models import Card
from ..serializers import CardSerializer

@csrf_exempt
@api_view(['POST', 'GET', 'DELETE', 'PATCH'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def CardCreateView(request, card_id=None):
    employee_id = request.query_params.get('employeeId', None)

    # Handle POST request
    if request.method == 'POST':
        serializer = CardSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
   
    # Handle GET request
    elif request.method == 'GET':
        board_id = request.query_params.get('boardId', None)
        role = request.query_params.get('role', None)

        # Check if the role is "Admin" and fetch all cards if true
        if role == "Admin":
            cards = Card.objects.all()  # Admin can view all cards
            if board_id:
                cards = cards.filter(boardId=board_id)  # Filter by boardId if provided
            serializer = CardSerializer(cards, many=True)
        else:
            if card_id:
                # Fetch specific card by cardId and boardId
                card = get_object_or_404(Card, cardId=card_id, boardId=board_id)
                serializer = CardSerializer(card)
            else:
                # Fetch all cards for the specific boardId
                cards = Card.objects.filter(boardId=board_id)

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
            data = request.data
            serializer = CardSerializer(card, data=data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


@csrf_exempt
@api_view(['DELETE'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
class CardDetail(APIView):
    def delete(self, request, pk, format=None):
        try:
            card = Card.objects.get(pk=pk)
            card.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Card.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        


@csrf_exempt
@api_view(['PUT'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def update_card(request, card_id):
    if request.method == 'PUT':
        try:
            card = Card.objects.get(cardId=card_id)
        except Card.DoesNotExist:
            return JsonResponse({'error': 'Card not found'}, status=404)

        data = json.loads(request.body)
        card.cardName = data.get('cardName', card.cardName)  # Update card name
        card.save()
        return JsonResponse({'cardId': card.cardId, 'cardName': card.cardName})
    


@csrf_exempt
@api_view(['POST', 'GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def save_description(request):
    if request.method == 'POST':
        try:
            # Parse the JSON data from the request body
            data = json.loads(request.body)

            # Get the cardId, boardId, and description from the request
            card_id = data.get('cardId')
            board_id = data.get('boardId')
            board_name = data.get('boardName')
            description = data.get('description')

            # Find the card with the given cardId and boardId
            card = Card.objects.get(
                cardId=card_id, boardId=board_id, boardName=board_name)

            # Update the description
            card.description = description
            card.save()

            return JsonResponse({"message": "Description updated successfully"})
        except Card.DoesNotExist:
            return JsonResponse({"error": "Card not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    elif request.method == 'GET':
        try:
            # Get cardId and boardId from request parameters
            card_id = request.GET.get('cardId')
            board_id = request.GET.get('boardId')

            # Find the card with the given cardId and boardId
            card = Card.objects.get(cardId=card_id, boardId=board_id)

            # Return the description in the response
            return JsonResponse({
                "cardId": card.cardId,
                "boardId": card.boardId,
                "description": card.description
            })
        except Card.DoesNotExist:
            return JsonResponse({"error": "Card not found"}, status=404)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)
    


@api_view(['PATCH'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def update_card_dates(request):
    print("Request Data:", request.data)
    card_id = request.data.get('cardId')
    if not card_id:
        return Response({"error": "cardId is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        card = Card.objects.get(cardId=card_id)
    except Card.DoesNotExist:
        return Response({"error": "Card not found."}, status=status.HTTP_404_NOT_FOUND)

    startdate = request.data.get('startdate')
    enddate = request.data.get('enddate')

    if startdate:
        try:
            card.startdate = datetime.fromisoformat(startdate)
        except ValueError:
            return Response({"error": "Invalid startdate format."}, status=status.HTTP_400_BAD_REQUEST)

    if enddate:
        try:
            card.enddate = datetime.fromisoformat(enddate)
        except ValueError:
            return Response({"error": "Invalid enddate format."}, status=status.HTTP_400_BAD_REQUEST)

    card.save()
    # Fixing the response return
    return Response(
        {'message': 'Date Updated successfully!'},
        status=status.HTTP_200_OK
    )



@csrf_exempt
@api_view(['GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def get_employee_cards(request, employee_id, board_id):
    if request.method == "GET":
        try:
            # Get cards where the employeeId directly matches and boardId is the same
            direct_cards = Card.objects.filter(employeeId=employee_id, boardId=board_id)
            # Get cards where employee appears in the 'members' JSON field
            additional_cards = []
            for card in Card.objects.filter(boardId=board_id):  # First filter by boardId
                members_field = card.members
                # Convert string to list if needed
                if isinstance(members_field, str):
                    try:
                        members_list = json.loads(members_field)  # Deserialize JSON
                    except json.JSONDecodeError:
                        members_list = []  # Set to empty if invalid JSON
                elif isinstance(members_field, list):
                    members_list = members_field  # Already a list, use as is
                else:
                    members_list = []  # If unexpected format, use empty list
                # Check if employeeId exists in members list
                if any(member.get("employeeId") == employee_id for member in members_list):
                    additional_cards.append(card)
            # Combine results and remove duplicates using a dictionary
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
            return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"error": "Invalid request method"}, status=400)