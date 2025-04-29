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

# Models and serializers
from ..serializers import EmployeeSerializer
from ..models import Employee

#permisiins disabled 
from rest_framework.decorators import api_view , permission_classes
from pyauth.auth import HasRoleAndDataPermission
from ..auth.permissions import SkipPermissionsIfDisabled

from dotenv import load_dotenv

load_dotenv()  # Load from .env if present

env_type = os.environ.get("ENV_CLASSIFICATION", "local")

mongo_uri = os.environ.get("GLOBAL_DB_HOST")
db_name = os.environ.get("TRACKER_DB_NAME")

if env_type == "test":
    client = MongoClient(mongo_uri)
else:
    client = MongoClient(mongo_uri, tls=True, tlsCAFile=certifi.where())




@csrf_exempt
@api_view(['POST'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def RegisterView(request):
    serializer = EmployeeSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Registration successful!'}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def change_password(request):
    # MongoDB connection
    fs = gridfs.GridFS(db_name)
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


# Login check through email and password


@csrf_exempt
@api_view(['POST'])
@permission_classes([SkipPermissionsIfDisabled, HasRoleAndDataPermission])
def LoginView(request):
    employee_id = request.data.get('employeeId')
    employee_name = request.data.get('employeeName')
    password = request.data.get('password')
    try:
        # Find the user by employeeId and employeeName
        user = Employee.objects.get(employeeId=employee_id, employeeName=employee_name)
        # Check if the password matches
        if check_password(password, user.password):
            # If password matches, login is successful
            return JsonResponse({
                'message': 'Login successful!',
                'employeeId': user.employeeId,
                'employeeName': user.employeeName,
                'email': user.email,
                'role': user.role  # Include role here
            }, status=status.HTTP_200_OK)
        else:
            # If password doesn't match
            return JsonResponse({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    except Employee.DoesNotExist:
        # If user with given employeeId and employeeName does not exist
        return JsonResponse({'error': 'User does not exist'}, status=status.HTTP_404_NOT_FOUND)
