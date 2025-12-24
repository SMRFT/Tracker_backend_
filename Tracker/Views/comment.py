from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework import status
import json
from django.http import JsonResponse, HttpResponse
from pyauth.auth import HasRolePermission
from ..models import Card
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

        new_comment = {
            "empid": str(data.get("employeeId")),
            "empname": data.get("employeeName"),
            "commenttext": data.get("text", ""),
            "date": data.get("date"),
            "time": data.get("time"),
            "file": file_meta
        }

        card.comment = normalize_comments(card.comment)
        card.comment.append(new_comment)
        card.save()

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

    for c in comments:
        if c.get("commenttext") == data.get("commenttext"):
            if c.get("file"):
                fs.delete(ObjectId(c["file"]["file_id"]))
        else:
            remaining.append(c)

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