from rest_framework.response import Response
from rest_framework import status

def api_success(data=None, message=None, status_code=status.HTTP_200_OK):
    """
    Returns a unified success response.
    """
    payload = {
        "success": True,
        "message": message,
        "data": data
    }
    return Response(payload, status=status_code)

def api_error(message, code="API_ERROR", details=None, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Returns a unified error response.
    """
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {}
        }
    }
    return Response(payload, status=status_code)
