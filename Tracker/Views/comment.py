from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
import json
from django.http import JsonResponse
from pyauth.auth import HasRolePermission
from ..models import Card
import logging

# Set up logging
logger = logging.getLogger(__name__)

@csrf_exempt
@api_view(['POST'])
@permission_classes([HasRolePermission])
def save_comment(request):
    """
    Save a comment to a card.
    Expected payload: {
        "cardId": "string",
        "boardId": "string",
        "auth-user-id": "string",  # Use auth-user-id instead of employeeId
        "employeeName": "string",
        "text": "string",
        "date": "YYYY-MM-DD",
        "time": "HH:MM:SS"
    }
    """
    if request.method == "POST":
        try:
            data = request.data  # Use request.data for DRF compatibility
            if not data:
                return JsonResponse({
                    "error": "No data provided",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate required fields
            required_fields = ['cardId', 'boardId', 'auth-user-id', 'employeeName', 'text', 'date', 'time']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                return JsonResponse({
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

            card_id = data.get('cardId')
            board_id = data.get('boardId')
            auth_user_id = data.get('auth-user-id')

            # Fetch the card and validate existence
            try:
                card = Card.objects.get(cardId=card_id, boardId=board_id)
            except Card.DoesNotExist:
                return JsonResponse({
                    "error": f"Card not found with cardId: {card_id} and boardId: {board_id}",
                    "success": False
                }, status=status.HTTP_404_NOT_FOUND)

            # Create new comment object
            new_comment = {
                "empid": str(auth_user_id),
                "empname": str(data.get("employeeName")),
                "commenttext": str(data.get("text")),
                "date": str(data.get("date")),
                "time": str(data.get("time"))
            }

            # Ensure comment field is a list
            if card.comment is None:
                card.comment = []
            elif isinstance(card.comment, str):
                try:
                    card.comment = json.loads(card.comment)
                except json.JSONDecodeError:
                    card.comment = []
            elif not isinstance(card.comment, list):
                card.comment = []

            # Append the new comment
            card.comment.append(new_comment)
            card.save()

            return JsonResponse({
                "message": "Comment saved successfully!",
                "success": True,
                "data": {
                    "comment": new_comment,
                    "total_comments": len(card.comment)
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Error saving comment: {str(e)}")
            return JsonResponse({
                "error": f"Internal server error: {str(e)}",
                "success": False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JsonResponse({
        "error": "Invalid request method. Only POST is allowed.",
        "success": False
    }, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@csrf_exempt
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_comments(request):
    if request.method == "GET":
        try:
            card_id = request.GET.get('cardId')
            board_id = request.GET.get('boardId')

            if not card_id or not board_id:
                return JsonResponse({
                    "error": "cardId and boardId are required",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

            card = Card.objects.get(cardId=card_id, boardId=board_id)
            comments = card.comment if card.comment and isinstance(card.comment, list) else []

            return JsonResponse({
                "comments": comments,
                "success": True
            }, status=status.HTTP_200_OK)

        except Card.DoesNotExist:
            return JsonResponse({
                "error": "Card not found",
                "success": False
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error getting comments: {str(e)}")
            return JsonResponse({
                "error": f"Internal server error: {str(e)}",
                "success": False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JsonResponse({
        "error": "Invalid request method. Only GET is allowed.",
        "success": False
    }, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@csrf_exempt
@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def delete_comment(request):
    """
    Delete a comment from a card.
    Expected payload: {
        "cardId": "string",
        "boardId": "string",
        "commenttext": "string"
    }
    """
    if request.method == "DELETE":
        try:
            data = request.data
            if not data:
                return JsonResponse({
                    "error": "No data provided",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

            required_fields = ['cardId', 'boardId', 'commenttext']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                return JsonResponse({
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

            card_id = data.get('cardId')
            board_id = data.get('boardId')
            comment_text_to_delete = data.get('commenttext')

            card = Card.objects.get(cardId=card_id, boardId=board_id)
            if card.comment is None or not isinstance(card.comment, list):
                return JsonResponse({
                    "error": "No comments found on this card",
                    "success": False
                }, status=status.HTTP_404_NOT_FOUND)

            original_count = len(card.comment)
            deleted_comment = None
            updated_comments = [c for c in card.comment if c.get('commenttext') != comment_text_to_delete]

            if len(updated_comments) == original_count:
                return JsonResponse({
                    "error": "Comment not found",
                    "success": False
                }, status=status.HTTP_404_NOT_FOUND)

            deleted_comment = next((c for c in card.comment if c.get('commenttext') == comment_text_to_delete), None)
            card.comment = updated_comments
            card.save()

            return JsonResponse({
                "message": "Comment deleted successfully!",
                "success": True,
                "data": {
                    "deletedComment": deleted_comment,
                    "remainingComments": len(updated_comments)
                }
            }, status=status.HTTP_200_OK)

        except Card.DoesNotExist:
            return JsonResponse({
                "error": f"Card not found with cardId: {card_id} and boardId: {board_id}",
                "success": False
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error deleting comment: {str(e)}")
            return JsonResponse({
                "error": f"Internal server error: {str(e)}",
                "success": False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JsonResponse({
        "error": "Invalid request method. Only DELETE is allowed.",
        "success": False
    }, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@csrf_exempt
@api_view(['PUT'])
@permission_classes([HasRolePermission])
def edit_comment(request):
    """
    Edit an existing comment on a card.
    Expected payload: {
        "cardId": "string",
        "boardId": "string",
        "originalCommentText": "string",
        "newCommentText": "string"
    }
    """
    if request.method == "PUT":
        try:
            data = request.data
            if not data:
                return JsonResponse({
                    "error": "No data provided",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

            required_fields = ['cardId', 'boardId', 'originalCommentText', 'newCommentText']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                return JsonResponse({
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

            card_id = data.get('cardId')
            board_id = data.get('boardId')
            original_comment_text = data.get('originalCommentText')
            new_comment_text = data.get('newCommentText').strip()

            if not new_comment_text:
                return JsonResponse({
                    "error": "New comment text cannot be empty",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

            card = Card.objects.get(cardId=card_id, boardId=board_id)
            if card.comment is None or not isinstance(card.comment, list):
                return JsonResponse({
                    "error": "No comments found on this card",
                    "success": False
                }, status=status.HTTP_404_NOT_FOUND)

            comment_found = False
            updated_comment = None

            for comment in card.comment:
                if comment.get('commenttext') == original_comment_text:
                    comment['commenttext'] = new_comment_text
                    comment_found = True
                    updated_comment = comment.copy()
                    break

            if not comment_found:
                return JsonResponse({
                    "error": "Original comment not found",
                    "success": False
                }, status=status.HTTP_404_NOT_FOUND)

            card.save()

            return JsonResponse({
                "message": "Comment updated successfully!",
                "success": True,
                "data": {
                    "updatedComment": updated_comment,
                    "originalText": original_comment_text,
                    "newText": new_comment_text
                }
            }, status=status.HTTP_200_OK)

        except Card.DoesNotExist:
            return JsonResponse({
                "error": f"Card not found with cardId: {card_id} and boardId: {board_id}",
                "success": False
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error editing comment: {str(e)}")
            return JsonResponse({
                "error": f"Internal server error: {str(e)}",
                "success": False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return JsonResponse({
        "error": "Invalid request method. Only PUT is allowed.",
        "success": False
    }, status=status.HTTP_405_METHOD_NOT_ALLOWED)