from pymongo import MongoClient
import gridfs
from rest_framework.decorators import api_view
from django.http import HttpResponse, Http404, JsonResponse
from rest_framework.response import Response
from datetime import datetime
from django.utils import timezone
from django.utils.timezone import now
from pymongo.errors import PyMongoError
import json
import certifi
import os
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser
from .parsers import MutableMultiPartParser, MutableFormParser
from pyauth.auth import HasRolePermission
from ..models import Card
from ..serializers import CardSerializer
from dotenv import load_dotenv

load_dotenv()  # Load from .env if present

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME", 'Tracker')
       

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri)


@csrf_exempt
@api_view(['POST', 'GET'])
@permission_classes([HasRolePermission])
def save_description(request):
    if request.method == 'POST':
        try:
           
            data = request.data          
            # Get the data from the request
            card_id = data.get('cardId')
            board_id = data.get('boardId')
            board_name = data.get('boardName')
            card_name = data.get('cardName')  # You're sending this but not using it
            description = data.get('description')

            print(f"Received data: cardId={card_id}, boardId={board_id}, boardName={board_name}, description={description}")

            # Validate required fields
            if not card_id or not board_id:
                return JsonResponse({"error": "cardId and boardId are required"}, status=400)

            # Find the card with the given cardId and boardId
            try:
                card = Card.objects.get(cardId=card_id, boardId=board_id)
                print(f"Found card: {card.cardName}")
            except Card.DoesNotExist:
                return JsonResponse({"error": "Card not found"}, status=404)

            from django.utils import timezone
            employee_id = request.data.get('auth-user-id') or data.get('employeeId')
            if employee_id:
                card.lastmodified_by = str(employee_id)
                card.lastmodified_date = timezone.now()

            # Update the description
            card.description = description or ""  # Handle None/empty descriptions
            card.save()

            return JsonResponse({
                "message": "Description updated successfully",
                "cardId": card.cardId,
                "boardId": card.boardId,
                "description": card.description
            })

        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            return JsonResponse({"error": "Invalid JSON data"}, status=400)
        except Exception as e:
            print(f"Error in save_description POST: {e}")
            return JsonResponse({"error": str(e)}, status=500)

    elif request.method == 'GET':
        try:
            # Get cardId and boardId from request parameters
            card_id = request.GET.get('cardId')
            board_id = request.GET.get('boardId')

            print(f"GET request: cardId={card_id}, boardId={board_id}")

            # Validate required fields
            if not card_id or not board_id:
                return JsonResponse({"error": "cardId and boardId are required"}, status=400)

            # Find the card with the given cardId and boardId
            try:
                card = Card.objects.get(cardId=card_id, boardId=board_id)
            except Card.DoesNotExist:
                return JsonResponse({"error": "Card not found"}, status=404)

            # Return the description in the response
            return JsonResponse({
                "cardId": card.cardId,
                "boardId": card.boardId,
                "cardName": card.cardName,
                "description": card.description or ""  # Handle None descriptions
            })

        except Exception as e:
            print(f"Error in save_description GET: {e}")
            return JsonResponse({"error": str(e)}, status=500)

    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)

@csrf_exempt
@api_view(['POST'])
@permission_classes([HasRolePermission])
@parser_classes([MutableMultiPartParser, MutableFormParser, JSONParser])
def upload_content(request):
    db = client[db_name]
    fs = gridfs.GridFS(db)
    response_data = {}

    from ..utils.auth import get_auth_user_id
    cardId = request.POST.get('cardId') or request.data.get('cardId')
    cardName = request.POST.get('cardName') or request.data.get('cardName')
    boardId = request.POST.get('boardId') or request.data.get('boardId')
    employeeId = request.POST.get('employeeId') or request.data.get('employeeId') or request.data.get('auth-user-id') or get_auth_user_id(request)
    employeeName = request.POST.get('employeeName') or request.data.get('employeeName') or request.data.get('auth-user-name') or "User"

    # Handle file upload
    if 'file' in request.FILES:
        file = request.FILES['file']
        file_id = fs.put(file, filename=file.name, cardId=cardId, cardName=cardName, boardId=boardId,
                         employeeId=employeeId, employeeName=employeeName, content_type=file.content_type)
        response_data['file_id'] = str(file_id)

    # Handle image upload
    if 'image' in request.FILES:
        image = request.FILES['image']
        image_id = fs.put(image, filename=image.name, cardId=cardId, cardName=cardName, boardId=boardId,
                          employeeId=employeeId, employeeName=employeeName, content_type=image.content_type)
        response_data['image_id'] = str(image_id)

    # Check if any file or image was uploaded
    if not response_data:
        return Response({'error': 'No file or image provided'}, status=400)

    return Response(response_data, status=201)


@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_file(request, board_id, card_id):
    db = client[db_name]          
    fs = gridfs.GridFS(db)
    employeeId = request.data.get('auth-user-id')
    employeeName = request.data.get('auth-user-name')

    try:
        # Query to find all files related to the given boardId and cardId
        files = list(fs.find({"boardId": board_id, "cardId": card_id}))

        if not files:
            return JsonResponse([], safe=False)

        files_data = [
            {
                "filename": file.filename,
                "cardId": getattr(file, 'cardId', None) or (file.metadata.get('cardId') if hasattr(file, 'metadata') and file.metadata else card_id),
                "cardName": getattr(file, 'cardName', None) or (file.metadata.get('cardName') if hasattr(file, 'metadata') and file.metadata else ''),
                "boardId": getattr(file, 'boardId', None) or (file.metadata.get('boardId') if hasattr(file, 'metadata') and file.metadata else board_id),
                "employeeId": employeeId or getattr(file, 'employeeId', None) or '',
                "employeeName": employeeName or getattr(file, 'employeeName', None) or '',
                "contentType": getattr(file, 'content_type', 'application/octet-stream'),
                "uploadDate": file.uploadDate.strftime("%Y-%m-%d %H:%M:%S") if hasattr(file, 'uploadDate') and isinstance(file.uploadDate, datetime) else "Invalid Date"
            }
            for file in files
        ]

        return JsonResponse(files_data, safe=False)

    except Exception as e:
        print(f"Error in get_file: {e}")
        return JsonResponse([], safe=False)

@api_view(['GET'])
@permission_classes([HasRolePermission])
def get_files(request):
    db = client[db_name]          
    fs = gridfs.GridFS(db)

    filename = request.GET.get('filename', '').strip()
    card_id = request.GET.get('cardId')
    board_id = request.GET.get('boardId')

    try:
        file = None
        if filename:
            file = fs.find_one({"filename": filename})
            if not file:
                import urllib.parse
                unquoted = urllib.parse.unquote(filename)
                file = fs.find_one({"filename": unquoted})
        
        if not file and card_id and board_id:
            file = fs.find_one({"cardId": card_id, "boardId": board_id})

        if not file:
            print(f"get_files: File not found for filename='{filename}', cardId='{card_id}'")
            return HttpResponse("File not found", status=404)

        content_type = getattr(file, 'content_type', 'application/octet-stream')
        response = HttpResponse(file.read(), content_type=content_type)
        
        import urllib.parse
        safe_filename = urllib.parse.quote(file.filename)
        response['Content-Disposition'] = f"inline; filename*=UTF-8''{safe_filename}"

        return response
    except Exception as e:
        print(f"Error in get_files: {e}")
        return HttpResponse("Error serving file", status=500)


def delete_file_from_gridfs(filename, board_id, card_id):
    db = client[db_name]          
    fs = gridfs.GridFS(db)
    # Find the file in GridFS
    file_data = db.fs.files.find_one(
        {'filename': filename, 'boardId': board_id, 'cardId': card_id})
    if file_data:
        # Delete the file from GridFS
        fs.delete(file_data['_id'])
        print(f"File {filename} deleted successfully.")
    else:
        print(f"File {filename} not found.")


@api_view(['DELETE'])
@permission_classes([HasRolePermission])
def delete_file(request, board_id, card_id, filename):
    if request.method == 'DELETE':
        if filename and board_id and card_id:
            # Call without the request parameter - only pass the 3 required arguments
            delete_file_from_gridfs(filename, board_id, card_id)
            return JsonResponse({'status': 'success'}, status=200)
        else:
            return JsonResponse({'status': 'error', 'message': 'Missing parameters'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)
