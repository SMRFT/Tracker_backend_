from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser
from .parsers import MutableMultiPartParser, MutableFormParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
import json
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from pyauth.auth import HasRolePermission
from ..models import Card, Notification
import logging
from pymongo import MongoClient
import gridfs
from bson import ObjectId
import os
from dotenv import load_dotenv
load_dotenv()  # Load from .env if present

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME", 'Tracker')

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri)

# Set up logging
logger = logging.getLogger(__name__)

db = client[db_name]

fs = gridfs.GridFS(db)

import uuid

def normalize_comments(comment):
    if not comment:
        return []
    if isinstance(comment, list):
        return comment
    if isinstance(comment, str):
        try:
            return json.loads(comment)
        except Exception:
            return []
    return []

@csrf_exempt
@api_view(['POST'])
@parser_classes([MutableMultiPartParser, MutableFormParser, JSONParser])
@permission_classes([HasRolePermission])
def save_comment(request):
    try:
        data = request.data
        uploaded_file = request.FILES.get("file")

        card = Card.objects.get(
            cardId=data.get("cardId"),
            boardId=data.get("boardId")
        )

        file_meta = None
        if uploaded_file:
            file_id = fs.put(
                uploaded_file,
                filename=uploaded_file.name,
                content_type=uploaded_file.content_type
            )
            file_meta = {
                "file_id": str(file_id),
                "file_name": uploaded_file.name,
                "content_type": uploaded_file.content_type,
                "file_url": f"/tracker/download_file/{file_id}/"
            }

        comment_id = str(uuid.uuid4())
        new_comment = {
            "commentId": comment_id,
            "empid": str(data.get("employeeId")),
            "empname": data.get("employeeName"),
            "commenttext": data.get("text", ""),
            "date": data.get("date"),
            "time": data.get("time"),
            "file": file_meta
        }

        employee_id = request.data.get('auth-user-id') or data.get("employeeId")
        if employee_id:
            card.lastmodified_by = str(employee_id)
            card.lastmodified_date = timezone.now()

        card.comment = normalize_comments(card.comment)
        card.comment.append(new_comment)
        card.save()

        # Handle mentions notifications and auto-add to members
        mentioned_json = request.POST.get("mentionedEmployees")
        if mentioned_json:
            import json
            try:
                mentioned_employees = json.loads(mentioned_json)
                current_member_ids = [str(m.get("employeeId")) for m in card.members] if card.members else []
                members_added = False

                for emp in mentioned_employees:
                    emp_id = str(emp.get("employeeId"))
                    # Prevent self-notification
                    if emp_id != str(data.get("employeeId")):
                        Notification.objects.create(
                            employeeId=emp_id,
                            cardId=card.cardId,
                            boardId=card.boardId,
                            message=f"{data.get('employeeName')} mentioned you in a comment on card '{card.cardName}'.",
                        )
                    # Auto-add to card if not already a member
                    if emp_id not in current_member_ids:
                        if not card.members:
                            card.members = []
                        # Provide default values in case employee object is missing fields
                        card.members.append({
                            "employeeId": emp_id,
                            "employeeName": emp.get("employeeName", "Unknown"),
                            "employeeEmail": emp.get("employeeEmail", ""),
                            "profilePictureUrl": emp.get("profilePictureUrl", "")
                        })
                        members_added = True
                        current_member_ids.append(emp_id)

                if members_added:
                    card.save()

            except Exception as e:
                logger.error(f"Error processing mentions: {e}")

        return JsonResponse({
            "success": True,
            "data": new_comment
        }, status=201)

    except Card.DoesNotExist:
        return JsonResponse({"success": False, "error": "Card not found"}, status=404)
    except Exception as e:
        logger.exception("Save comment failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)
    
@csrf_exempt
@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_comments(request):
    try:
        card = Card.objects.get(
            cardId=request.GET.get("cardId"),
            boardId=request.GET.get("boardId")
        )

        comments = normalize_comments(card.comment)

        # expose file_url for frontend
        for c in comments:
            if c.get("file"):
                c["file_url"] = c["file"].get("file_url")

        return JsonResponse({
            "success": True,
            "comments": comments
        }, status=200)

    except Card.DoesNotExist:
        return JsonResponse({"success": False, "error": "Card not found"}, status=404)
    
@csrf_exempt
@api_view(['GET'])
@permission_classes([HasRolePermission])
def download_file(request, file_id):
    try:
        f = fs.get(ObjectId(file_id))
        response = HttpResponse(f.read(), content_type=f.content_type)
        response["Content-Disposition"] = f'inline; filename="{f.filename}"'
        return response
    except Exception:
        return JsonResponse({"error": "File not found"}, status=404)

@csrf_exempt
@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def delete_comment(request):
    data = request.data
    card = Card.objects.get(
        cardId=data.get("cardId"),
        boardId=data.get("boardId")
    )

    comments = normalize_comments(card.comment)
    remaining = []

    allowed_actions = request.data.get('auth-allowed-action-codes', [])
    is_admin = "ST-R-A" in allowed_actions or "ST-R-HOD" in allowed_actions
    authenticated_user_id = request.data.get("auth-user-id")

    comment_id = data.get("commentId")
    comment_text = data.get("commenttext")

    for c in comments:
        is_match = False
        if comment_id and c.get("commentId") == comment_id:
            is_match = True
        elif not comment_id and c.get("commenttext") == comment_text:
            is_match = True

        if is_match:
            if not is_admin and str(c.get("empid")) != str(authenticated_user_id):
                return JsonResponse({"success": False, "error": "Permission denied: You cannot delete another user's comment."}, status=status.HTTP_403_FORBIDDEN)
            if c.get("file"):
                fs.delete(ObjectId(c["file"]["file_id"]))
        else:
            remaining.append(c)

    employee_id = request.data.get('auth-user-id') or data.get("employeeId")
    if employee_id:
        card.lastmodified_by = str(employee_id)
        card.lastmodified_date = timezone.now()
    card.comment = remaining
    card.save()

    return JsonResponse({"success": True})


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

            required_fields = ['cardId', 'boardId', 'newCommentText']
            missing_fields = [field for field in required_fields if not data.get(field)]
            if missing_fields:
                return JsonResponse({
                    "error": f"Missing required fields: {', '.join(missing_fields)}",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

            card_id = data.get('cardId')
            board_id = data.get('boardId')
            comment_id = data.get('commentId')
            original_comment_text = data.get('originalCommentText')
            new_comment_text = data.get('newCommentText').strip()

            if not comment_id and not original_comment_text:
                return JsonResponse({
                    "error": "Either commentId or originalCommentText is required",
                    "success": False
                }, status=status.HTTP_400_BAD_REQUEST)

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

            allowed_actions = request.data.get('auth-allowed-action-codes', [])
            is_admin = "ST-R-A" in allowed_actions or "ST-R-HOD" in allowed_actions
            authenticated_user_id = request.data.get("auth-user-id")

            comment_found = False
            updated_comment = None

            for comment in card.comment:
                is_match = False
                if comment_id and comment.get('commentId') == comment_id:
                    is_match = True
                elif not comment_id and comment.get('commenttext') == original_comment_text:
                    is_match = True

                if is_match:
                    if not is_admin and str(comment.get("empid")) != str(authenticated_user_id):
                        return JsonResponse({
                            "error": "Permission denied: You cannot edit another user's comment.",
                            "success": False
                        }, status=status.HTTP_403_FORBIDDEN)
                    comment['commenttext'] = new_comment_text
                    comment_found = True
                    updated_comment = comment.copy()
                    break

            if not comment_found:
                return JsonResponse({
                    "error": "Original comment not found",
                    "success": False
                }, status=status.HTTP_404_NOT_FOUND)

            employee_id = request.data.get('auth-user-id') or data.get("employeeId")
            if employee_id:
                card.lastmodified_by = str(employee_id)
                card.lastmodified_date = timezone.now()
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


@csrf_exempt
@api_view(['POST'])
@permission_classes([HasRolePermission])
def react_comment(request):
    """
    Toggle a reaction emoji on a comment.
    Payload: {
        "cardId": "...",
        "boardId": "...",
        "commentId": "...",
        "emoji": "👍",
        "employeeId": "1001",
        "employeeName": "John Doe"
    }
    """
    try:
        data = request.data
        card_id = data.get("cardId")
        board_id = data.get("boardId")
        comment_id = data.get("commentId")
        comment_text = data.get("commenttext")
        emoji = data.get("emoji")
        emp_id = str(data.get("employeeId"))
        emp_name = data.get("employeeName")

        if not card_id or not board_id or not emoji or not emp_id:
            return JsonResponse({"success": False, "error": "Missing required fields"}, status=400)

        card = Card.objects.get(cardId=card_id, boardId=board_id)
        comments = normalize_comments(card.comment)

        updated_comment = None
        for comment in comments:
            is_match = False
            if comment_id and comment.get("commentId") == comment_id:
                is_match = True
            elif comment_text and comment.get("commenttext") == comment_text:
                is_match = True

            if is_match:
                reactions = comment.get("reactions", {})
                if not isinstance(reactions, dict):
                    reactions = {}

                users_reacted = reactions.get(emoji, [])
                if not isinstance(users_reacted, list):
                    users_reacted = []

                # Toggle user reaction
                already_reacted = any(str(u.get("employeeId")) == emp_id for u in users_reacted)
                if already_reacted:
                    users_reacted = [u for u in users_reacted if str(u.get("employeeId")) != emp_id]
                else:
                    users_reacted.append({"employeeId": emp_id, "employeeName": emp_name})

                if users_reacted:
                    reactions[emoji] = users_reacted
                else:
                    reactions.pop(emoji, None)

                comment["reactions"] = reactions
                updated_comment = comment
                break

        if updated_comment:
            card.comment = comments
            employee_id = request.data.get('auth-user-id')
            if employee_id:
                card.lastmodified_by = str(employee_id)
                card.lastmodified_date = timezone.now()
            card.save()
            return JsonResponse({"success": True, "comment": updated_comment})

        return JsonResponse({"success": False, "error": "Comment not found"}, status=404)

    except Card.DoesNotExist:
        return JsonResponse({"success": False, "error": "Card not found"}, status=404)
    except Exception as e:
        logger.exception("React to comment failed")
        return JsonResponse({"success": False, "error": str(e)}, status=500)