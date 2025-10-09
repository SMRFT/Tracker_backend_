# security.py
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth.hashers import check_password, make_password
from pymongo import MongoClient
import certifi
#from rest_framework_simplejwt.tokens import RefreshToken
import os
from dotenv import load_dotenv
from pyauth.auth import HasRolePermission

load_dotenv()
env_type = os.environ.get("ENV_CLASSIFICATION", "local")
mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME")

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri, tls=True, tlsAllowInvalidCertificates=True, tlsCAFile=certifi.where())

db = client[db_name]
collection = db.Tracker_employee

@api_view(['POST'])
@csrf_exempt
def login(request):
    employee_id = request.data.get("employeeId", "").strip()
    employee_name = request.data.get("employeeName", "").strip()
    password = request.data.get("password")

    if not (employee_id and employee_name and password):
        return Response(
            {"error": "Employee ID, Name, and Password are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    employee = collection.find_one({"employeeId": employee_id, "employeeName": employee_name})
    if not employee:
        return Response(
            {"error": "Employee not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    if not check_password(password, employee["password"]):
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED
        )

    user = {"username": employee_id, "auth-user-id": employee_id}  # Include auth-user-id in token payload
    refresh = RefreshToken.for_user(user)
    return Response({
        "access_token": str(refresh.access_token),
        "auth-user-id": employee_id,
        "employeeName": employee_name,
        "email": employee.get("email", f"{employee_id}@example.com"),
        "role": employee.get("role", "Employee")
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([HasRolePermission])
def change_password(request):
    auth_user_id = request.data.get('auth-user-id')
    email = request.data.get('email', '').strip()
    current_password = request.data.get('currentPassword')
    new_password = request.data.get('newPassword')

    if not auth_user_id or not email or not current_password or not new_password:
        return Response({"error": "Missing fields"}, status=status.HTTP_400_BAD_REQUEST)

    employee = collection.find_one({"employeeId": auth_user_id, "email": email})
    if not employee:
        return Response({"error": "Employee not found"}, status=status.HTTP_404_NOT_FOUND)

    if not check_password(current_password, employee["password"]):
        return Response({"error": "Incorrect current password"}, status=status.HTTP_400_BAD_REQUEST)

    hashed_new_password = make_password(new_password)
    collection.update_one(
        {"employeeId": auth_user_id, "email": email},
        {"$set": {"password": hashed_new_password}}
    )
    return Response({"message": "Password updated successfully"}, status=status.HTTP_200_OK)

