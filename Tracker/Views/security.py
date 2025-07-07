from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import os
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.hashers import make_password, check_password
from pymongo import MongoClient
import gridfs
import certifi
from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRolePermission


from dotenv import load_dotenv

load_dotenv()  # Load from .env if present

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME")

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri, tls=True,tlsAllowInvalidCertificates=True,tlsCAFile=certifi.where())


@api_view(['POST'])
@permission_classes([ HasRolePermission])
def change_password(request):
    employee_id = request.data['auth-user-id']
    # MongoDB connection
    db = client[db_name]          
    fs = gridfs.GridFS(db)
    collection = db.Tracker_employee

    # Get and clean data from the request
    # Strip any leading/trailing spaces
    email = request.data.get('email', '').strip()
    employee_id = request.data.get(
        'employeeId', '').strip()  # Same for employeeId
    current_password = request.data.get('currentPassword')
    new_password = request.data.get('newPassword')

    # Check for missing fields
    if not email or not employee_id or not current_password or not new_password:
        return Response({"error": "Missing fields"}, status=status.HTTP_400_BAD_REQUEST)

    # Find the employee by email and employeeId in MongoDB
    employee = collection.find_one({"email": email, "employeeId": employee_id})

    if not employee:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

    # Check if current password matches
    if not check_password(current_password, employee['password']):
        return Response({"error": "Incorrect current password"}, status=status.HTTP_400_BAD_REQUEST)

    # Hash the new password and update it in the database
    hashed_new_password = make_password(new_password)
    collection.update_one(
        {"email": email, "employeeId": employee_id},
        {"$set": {"password": hashed_new_password}}
    )

    return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)
