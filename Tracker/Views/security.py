from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from django.contrib.auth.hashers import check_password, make_password
from rest_framework_simplejwt.tokens import RefreshToken
from pyauth.auth import HasRolePermission
from ..utils.db import get_tracker_db
from ..utils.auth import get_auth_user_id
from ..utils.responses import api_success, api_error

db = get_tracker_db()
collection = db["Tracker_employee"] 

@api_view(['POST'])
@csrf_exempt
def login(request):
    employee_id = request.data.get("employeeId", "").strip()
    employee_name = request.data.get("employeeName", "").strip()
    password = request.data.get("password")

    if not (employee_id and employee_name and password):
        return api_error(
            "Employee ID, Name, and Password are required",
            code="INVALID_PAYLOAD",
            status_code=status.HTTP_400_BAD_REQUEST
        )

    employee = collection.find_one({"employeeId": employee_id, "employeeName": employee_name})
    if not employee:
        return api_error(
            "Employee not found",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )

    if not check_password(password, employee["password"]):
        return api_error(
            "Invalid credentials",
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    user = {"username": employee_id, "auth-user-id": employee_id}  # Include auth-user-id in token payload
    refresh = RefreshToken.for_user(user)
    
    data = {
        "access_token": str(refresh.access_token),
        "auth-user-id": employee_id,
        "employeeName": employee_name,
        "email": employee.get("email", f"{employee_id}@example.com"),
        "role": employee.get("role", "Employee")
    }
    return api_success(data, message="Login successful")

@api_view(['POST'])
@permission_classes([HasRolePermission])
def change_password(request):
    auth_user_id = get_auth_user_id(request)
    email = request.data.get('email', '').strip()
    current_password = request.data.get('currentPassword')
    new_password = request.data.get('newPassword')
    
    if not auth_user_id or not email or not current_password or not new_password:
        return api_error("Missing fields", code="INVALID_PAYLOAD", status_code=status.HTTP_400_BAD_REQUEST)

    employee = collection.find_one({"employeeId": auth_user_id, "email": email})
    if not employee:
        return api_error("Employee not found", code="NOT_FOUND", status_code=status.HTTP_404_NOT_FOUND)

    if not check_password(current_password, employee["password"]):
        return api_error("Incorrect current password", code="INVALID_PASSWORD", status_code=status.HTTP_400_BAD_REQUEST)

    hashed_new_password = make_password(new_password)
    collection.update_one(
        {"employeeId": auth_user_id, "email": email},
        {"$set": {"password": hashed_new_password}}
    )
    return api_success(message="Password updated successfully")
