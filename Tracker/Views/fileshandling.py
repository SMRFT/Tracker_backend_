from pymongo import MongoClient
import gridfs
from rest_framework.decorators import api_view
from django.http import HttpResponse, Http404, JsonResponse
from rest_framework.response import Response
from datetime import datetime
from pymongo.errors import PyMongoError
import json
import certifi
import os
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRolePermission
from dotenv import load_dotenv

load_dotenv()  # Load from .env if present

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("TRACKER_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME")
       

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri, tls=True,tlsAllowInvalidCertificates=True,tlsCAFile=certifi.where())




@csrf_exempt
@api_view(['POST'])
@permission_classes([ HasRolePermission])
def upload_content(request):
    db = client[db_name]          
    fs = gridfs.GridFS(db)
    response_data = {}

    # Extract card-related details from the request
    cardId = request.POST.get('cardId')
    cardName = request.POST.get('cardName')
    boardId = request.POST.get('boardId')
    employeeId = request.data.get('auth-user-id')
    employeeName = request.data.get('auth-user-name')

    # Handle file upload
    if 'file' in request.FILES:
        file = request.FILES['file']
        file_id = fs.put(file, filename=file.name, cardId=cardId, cardName=cardName, boardId=boardId,
                         employeeId=employeeId, employeeName=employeeName, cardcontent_type=file.content_type)
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
@permission_classes([ HasRolePermission])
def get_file(request, board_id, card_id):
    db = client[db_name]          
    fs = gridfs.GridFS(db)
    employeeId = request.data.get('auth-user-id')
    employeeName = request.data.get('auth-user-name')

    try:
        # Query to find all files related to the given boardId and cardId
        files = list(fs.find({"boardId": board_id, "cardId": card_id}))

        # If no files are found, return an empty list
        if not files:
            return JsonResponse([], safe=False)

        # List to store file details
        files_data = [
            {
                "filename": file.filename,
                "cardId": file.cardId,
                "cardName": file.cardName,
                "boardId": file.boardId,
                "employeeId": employeeId,
                "employeeName": employeeName,
                "contentType": file.content_type,
                "uploadDate": file.uploadDate.strftime("%Y-%m-%d %H:%M:%S") if isinstance(file.uploadDate, datetime) else "Invalid Date"
            }
            for file in files
        ]

        return JsonResponse(files_data, safe=False)

    except PyMongoError:
        raise Http404("Error retrieving files")

@api_view(['GET'])
@permission_classes([ HasRolePermission])
def get_files(request):
    db = client[db_name]          
    fs = gridfs.GridFS(db)

    employeeId = request.data.get('auth-user-id')
    employeeName = request.data.get('auth-user-name')

    
    # Retrieve and clean filename from query parameters
    filename = request.GET.get('filename', '').strip()  # Trim whitespace

    try:
        file = fs.find_one({"filename": filename})
        if not file:
            raise Http404("File not found")

        response = HttpResponse(file.read(), content_type=file.content_type)
        response['Content-Disposition'] = f'attachment; filename="{file.filename}"'

        response['X-File-Metadata'] = json.dumps({
            "filename": file.filename,
            "cardId": file.cardId,
            "cardName": file.cardName,
            "boardId": file.boardId,
            "employeeId": employeeId,
            "employeeName": employeeName,
            "contentType": file.content_type,
            "uploadDate": file.uploadDate.strftime("%Y-%m-%d %H:%M:%S") if isinstance(file.uploadDate, datetime) else "Invalid Date"
        })

        return response
    except PyMongoError:
        raise Http404("File not found")

@api_view(['DELETE'])
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
@permission_classes([ HasRolePermission])
def delete_file(request, board_id, card_id, filename):
    if request.method == 'DELETE':
        if filename and board_id and card_id:
            delete_file_from_gridfs(filename, board_id, card_id)
            return JsonResponse({'status': 'success'}, status=200)
        else:
            return JsonResponse({'status': 'error', 'message': 'Missing parameters'}, status=400)

    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=400)
