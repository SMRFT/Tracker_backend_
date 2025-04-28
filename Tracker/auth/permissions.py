# permissions.py


import os
from rest_framework.permissions import BasePermission

class SkipPermissionsIfDisabled(BasePermission):
    def has_permission(self, request, view):
        security_disabled = os.environ.get("SECURITY_DISABLED", "false").lower() == "true"
        if security_disabled:
            return True
        return False  # Otherwise, let the next permission class handle

