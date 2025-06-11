from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
import json
from django.http import JsonResponse
from pyauth.auth import HasRolePermission
from ..models import Card

@csrf_exempt
@api_view(['POST'])
@permission_classes([HasRolePermission])
def save_comment(request):
    """
    Save a comment to a card.
    Expected payload: {
        "cardId": "string",
        "boardId": "string", 
        "employeeId": "string",
        "employeeName": "string",
        "text": "string",
        "date": "YYYY-MM-DD",
        "time": "HH:MM:SS"
    }
    """
    if request.method == "POST":
        try:
            # Use request.data instead of request.body for DRF
            # This handles both form data and JSON automatically
            if hasattr(request, 'data'):
                data = request.data
            else:
                # Fallback for raw Django requests
                try:
                    data = json.loads(request.body.decode('utf-8'))
                except json.JSONDecodeError:
                    return JsonResponse({
                        "error": "Invalid JSON format",
                        "success": False
                    }, status=400)
            
            # Validate required fields
            required_fields = ['cardId', 'boardId', 'employeeId', 'employeeName', 'text', 'date', 'time']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return JsonResponse({
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "success": False
                }, status=400)
            
            cardId = data.get('cardId')
            boardId = data.get('boardId')
            
            # Fetch the card based on cardId and boardId
            try:
                card = Card.objects.get(cardId=cardId, boardId=boardId)
            except Card.DoesNotExist:
                return JsonResponse({
                    "error": f"Card not found with cardId: {cardId} and boardId: {boardId}",
                    "success": False
                }, status=404)
            
            # Create new comment object
            new_comment = {
                "empid": str(data.get("employeeId")),
                "empname": str(data.get("employeeName")),
                "commenttext": str(data.get("text")),
                "date": str(data.get("date")),
                "time": str(data.get("time"))
            }
            
            # Initialize or validate comment field
            if card.comment is None:
                card.comment = []
            elif not isinstance(card.comment, list):
                try:
                    # Attempt to parse it as JSON if it's a string
                    if isinstance(card.comment, str):
                        card.comment = json.loads(card.comment)
                    else:
                        card.comment = []
                except (json.JSONDecodeError, TypeError):
                    card.comment = []
            
            # Append the new comment
            card.comment.append(new_comment)
            
            # Save the card
            card.save()
            
            return JsonResponse({
                "message": "Comment saved successfully!",
                "success": True,
                "data": {
                    "comment": new_comment,
                    "total_comments": len(card.comment)
                }
            }, status=200)
            
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error saving comment: {str(e)}")
            
            return JsonResponse({
                "error": f"Internal server error: {str(e)}",
                "success": False
            }, status=500)
    
    return JsonResponse({
        "error": "Invalid request method. Only POST is allowed.",
        "success": False
    }, status=405)


@csrf_exempt
@api_view(['GET'])
@permission_classes([ HasRolePermission])
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


from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
import json
from django.http import JsonResponse
from pyauth.auth import HasRolePermission
from ..models import Card

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
            # Use request.data instead of request.body for DRF
            if hasattr(request, 'data'):
                data = request.data
            else:
                # Fallback for raw Django requests
                try:
                    data = json.loads(request.body.decode('utf-8'))
                except json.JSONDecodeError:
                    return JsonResponse({
                        "error": "Invalid JSON format",
                        "success": False
                    }, status=400)
            
            # Validate required fields
            required_fields = ['cardId', 'boardId', 'commenttext']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return JsonResponse({
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "success": False
                }, status=400)
            
            cardId = data.get('cardId')
            boardId = data.get('boardId')
            comment_text_to_delete = data.get('commenttext')
            
            # Fetch the card based on cardId and boardId
            try:
                card = Card.objects.get(cardId=cardId, boardId=boardId)
            except Card.DoesNotExist:
                return JsonResponse({
                    "error": f"Card not found with cardId: {cardId} and boardId: {boardId}",
                    "success": False
                }, status=404)
            
            # Initialize or validate comment field
            if card.comment is None or len(card.comment) == 0:
                return JsonResponse({
                    "error": "No comments found on this card",
                    "success": False
                }, status=404)
            
            # Ensure card.comment is a list
            if not isinstance(card.comment, list):
                try:
                    if isinstance(card.comment, str):
                        card.comment = json.loads(card.comment)
                    else:
                        return JsonResponse({
                            "error": "Invalid comment format in database",
                            "success": False
                        }, status=500)
                except (json.JSONDecodeError, TypeError):
                    return JsonResponse({
                        "error": "Cannot parse existing comments",
                        "success": False
                    }, status=500)
            
            # Find and remove the comment
            original_count = len(card.comment)
            deleted_comment = None
            
            # Filter out the comment to be deleted
            updated_comments = []
            for comment in card.comment:
                if comment.get('commenttext') == comment_text_to_delete:
                    deleted_comment = comment.copy()  # Save for response
                else:
                    updated_comments.append(comment)
            
            # Check if comment was found and deleted
            if len(updated_comments) == original_count:
                return JsonResponse({
                    "error": "Comment not found",
                    "success": False
                }, status=404)
            
            # Update the card with the filtered comments
            card.comment = updated_comments
            card.save()
            
            return JsonResponse({
                "message": "Comment deleted successfully!",
                "success": True,
                "data": {
                    "deletedComment": deleted_comment,
                    "remainingComments": len(updated_comments)
                }
            }, status=200)
            
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error deleting comment: {str(e)}")
            
            return JsonResponse({
                "error": f"Internal server error: {str(e)}",
                "success": False
            }, status=500)
    
    return JsonResponse({
        "error": "Invalid request method. Only DELETE is allowed.",
        "success": False
    }, status=405)




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
            # Use request.data instead of request.body for DRF
            if hasattr(request, 'data'):
                data = request.data
            else:
                # Fallback for raw Django requests
                try:
                    data = json.loads(request.body.decode('utf-8'))
                except json.JSONDecodeError:
                    return JsonResponse({
                        "error": "Invalid JSON format",
                        "success": False
                    }, status=400)
            
            # Validate required fields
            required_fields = ['cardId', 'boardId', 'originalCommentText', 'newCommentText']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            if missing_fields:
                return JsonResponse({
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "success": False
                }, status=400)
            
            cardId = data.get('cardId')
            boardId = data.get('boardId')
            original_comment_text = data.get('originalCommentText')
            new_comment_text = data.get('newCommentText')
            
            # Validate that new comment text is not empty
            if not new_comment_text.strip():
                return JsonResponse({
                    "error": "New comment text cannot be empty",
                    "success": False
                }, status=400)
            
            # Fetch the card based on cardId and boardId
            try:
                card = Card.objects.get(cardId=cardId, boardId=boardId)
            except Card.DoesNotExist:
                return JsonResponse({
                    "error": f"Card not found with cardId: {cardId} and boardId: {boardId}",
                    "success": False
                }, status=404)
            
            # Initialize or validate comment field
            if card.comment is None:
                return JsonResponse({
                    "error": "No comments found on this card",
                    "success": False
                }, status=404)
            
            # Ensure card.comment is a list
            if not isinstance(card.comment, list):
                try:
                    if isinstance(card.comment, str):
                        card.comment = json.loads(card.comment)
                    else:
                        return JsonResponse({
                            "error": "Invalid comment format in database",
                            "success": False
                        }, status=500)
                except (json.JSONDecodeError, TypeError):
                    return JsonResponse({
                        "error": "Cannot parse existing comments",
                        "success": False
                    }, status=500)
            
            # Find and update the comment
            comment_found = False
            updated_comment = None
            
            for comment in card.comment:
                if comment.get('commenttext') == original_comment_text:
                    # Update the comment text while preserving other fields
                    comment['commenttext'] = new_comment_text.strip()
                    comment_found = True
                    updated_comment = comment.copy()  # For response
                    break
            
            if not comment_found:
                return JsonResponse({
                    "error": "Original comment not found",
                    "success": False
                }, status=404)
            
            # Save the updated card
            card.save()
            
            return JsonResponse({
                "message": "Comment updated successfully!",
                "success": True,
                "data": {
                    "updatedComment": updated_comment,
                    "originalText": original_comment_text,
                    "newText": new_comment_text
                }
            }, status=200)
            
        except Exception as e:
            # Log the error for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error editing comment: {str(e)}")
            
            return JsonResponse({
                "error": f"Internal server error: {str(e)}",
                "success": False
            }, status=500)
    
    return JsonResponse({
        "error": "Invalid request method. Only PUT is allowed.",
        "success": False
    }, status=405)