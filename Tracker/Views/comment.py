from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import json
from django.http import JsonResponse
from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRolePermission
from ..auth.permissions import SkipPermissionsIfDisabled
from ..models import Card


@csrf_exempt
@api_view(['POST'])
@permission_classes([SkipPermissionsIfDisabled, HasRolePermission])
def save_comment(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            cardId = data.get('cardId')
            # Ensure you're using the correct field name
            boardId = data.get('boardId')

            # Fetch the card based on cardId and boardId
            card = Card.objects.get(cardId=cardId, boardId=boardId)

            new_comment = {
                "empid": data.get("employeeId"),
                "empname": data.get("employeeName"),
                "commenttext": data.get("text"),
                "date": data.get("date"),
                "time": data.get("time")
            }

            # If card.comment is None, initialize it as an empty list
            if card.comment is None:
                card.comment = []

            # Ensure card.comment is a list
            if not isinstance(card.comment, list):
                try:
                    # Attempt to parse it as a list
                    card.comment = json.loads(card.comment)
                except (json.JSONDecodeError, TypeError):
                    card.comment = []  # Initialize as an empty list if it's invalid

            # Append the new comment to the existing comments
            card.comment.append(new_comment)
            card.save()

            return JsonResponse({"message": "Comment saved successfully!"}, status=200)
        except Card.DoesNotExist:
            return JsonResponse({"error": "Card not found"}, status=404)
    return JsonResponse({"error": "Invalid request method"}, status=400)


@csrf_exempt
@api_view(['GET'])
@permission_classes([SkipPermissionsIfDisabled, HasRolePermission])
def get_comments(request):
    if request.method == "GET":
        try:
            cardId = request.GET.get('cardId')
            boardId = request.GET.get('boardId')

            # Fetch the card based on cardId and boardId
            card = Card.objects.get(cardId=cardId, boardId=boardId)

            # If comments are None, return an empty list
            comments = card.comment if card.comment is not None else []

            return JsonResponse({"comments": comments}, status=200)

        except Card.DoesNotExist:
            return JsonResponse({"error": "Card not found"}, status=404)
    return JsonResponse({"error": "Invalid request method"}, status=400)


@csrf_exempt
@api_view(['DELETE'])
@permission_classes([SkipPermissionsIfDisabled, HasRolePermission])
def delete_comment(request):
    if request.method == "DELETE":
        try:
            data = json.loads(request.body)
            cardId = data.get('cardId')
            boardId = data.get('boardId')
            commenttext = data.get('commenttext')

            # Fetch the card based on cardId and boardId
            card = Card.objects.get(cardId=cardId, boardId=boardId)

            # Ensure card.comment is a list
            if not isinstance(card.comment, list):
                try:
                    # Attempt to parse it as a list
                    card.comment = json.loads(card.comment)
                except (json.JSONDecodeError, TypeError):
                    return JsonResponse({"error": "Invalid comment format"}, status=400)

            # Find and remove the comment with the matching commenttext
            updated_comments = [comment for comment in card.comment if comment.get(
                'commenttext') != commenttext]

            if len(updated_comments) == len(card.comment):
                return JsonResponse({"error": "Comment not found"}, status=404)

            # Update the card with the new list of comments
            card.comment = updated_comments
            card.save()

            return JsonResponse({"message": "Comment deleted successfully!"}, status=200)

        except Card.DoesNotExist:
            return JsonResponse({"error": "Card not found"}, status=404)

        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=400)




@csrf_exempt
@api_view(['PUT'])
@permission_classes([SkipPermissionsIfDisabled, HasRolePermission])
def edit_comment(request):
    if request.method == "PUT":
        try:
            data = json.loads(request.body)
            cardId = data.get('cardId')
            boardId = data.get('boardId')
            original_comment_text = data.get('originalCommentText')
            new_comment_text = data.get('newCommentText')
            # Fetch the card based on cardId and boardId
            card = Card.objects.get(cardId=cardId, boardId=boardId)
            # Ensure card.comment is a list
            if not isinstance(card.comment, list):
                try:
                    # Attempt to parse it as a list
                    card.comment = json.loads(card.comment)
                except (json.JSONDecodeError, TypeError):
                    return JsonResponse({"error": "Invalid comment format"}, status=400)
            # Find the comment to edit
            updated_comments = []
            comment_found = False
            for comment in card.comment:
                if comment.get('commenttext') == original_comment_text:
                    # Update the comment text
                    comment['commenttext'] = new_comment_text
                    comment_found = True
                updated_comments.append(comment)
            if not comment_found:
                return JsonResponse({"error": "Comment not found"}, status=404)
            # Update the card with the edited list of comments
            card.comment = updated_comments
            card.save()
            return JsonResponse({"message": "Comment updated successfully!"}, status=200)
        except Card.DoesNotExist:
            return JsonResponse({"error": "Card not found"}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON format"}, status=400)
    return JsonResponse({"error": "Invalid request method"}, status=400)
