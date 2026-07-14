import logging
from django.http import Http404
from django.core.exceptions import PermissionDenied
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status

logger = logging.getLogger(__name__)

def custom_api_exception_handler(exc, context):
    """
    Custom exception handler to standardize API error formats.
    """
    # Call DRF's standard exception handler first to get the standard response
    response = exception_handler(exc, context)

    # Convert standard Django exceptions to DRF equivalent errors
    if isinstance(exc, Http404):
        response = Response({'detail': 'Not Found.'}, status=status.HTTP_404_NOT_FOUND)
    elif isinstance(exc, PermissionDenied):
        response = Response({'detail': 'Permission Denied.'}, status=status.HTTP_403_FORBIDDEN)

    if response is not None:
        error_details = response.data
        message = "An API error occurred."
        code = getattr(exc, 'default_code', 'API_ERROR')

        if isinstance(error_details, dict):
            if 'detail' in error_details:
                message = error_details.pop('detail')
            elif error_details:
                message = "Validation failed"
                code = "VALIDATION_FAILED"

        response.data = {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": error_details
            }
        }
    else:
        # Handle unhandled Exceptions (e.g. database disconnects, programming errors)
        view_name = context['view'].__class__.__name__ if 'view' in context else 'UnknownView'
        logger.exception(f"Unhandled exception in view: {view_name}")
        
        response = Response({
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "A critical system error occurred.",
                "details": {}
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
