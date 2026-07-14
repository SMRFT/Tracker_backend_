from pyauth.jwt_check import isSecurityDisabled

def get_auth_user_id(request):
    """
    Extracts the authenticated user ID from the request body, header, or query parameters.
    Handles fallback when security check is disabled.
    """
    # Prefer retrieving from request.data (injected by permissions middleware)
    employee_id = request.data.get('auth-user-id')
    if not employee_id:
        if isSecurityDisabled():
            employee_id = (
                request.headers.get('auth-user-id') or
                request.query_params.get('auth-user-id')
            )
    return str(employee_id) if employee_id else None

def get_user_role(request):
    """
    Resolves the standard role string ("Admin", "HOD", or "Employee") 
    based on the actions allowed in the token metadata.
    """
    allowed_actions = request.data.get('auth-allowed-action-codes', [])
    if "ST-R-A" in allowed_actions:
        return "Admin"
    elif "ST-R-HOD" in allowed_actions:
        return "HOD"
    return "Employee"

def is_admin_user(request):
    """
    Returns True if the authenticated user has Admin permissions.
    """
    return get_user_role(request) == "Admin"

def is_admin_or_hod_user(request):
    """
    Returns True if the authenticated user has Admin or HOD permissions.
    """
    return get_user_role(request) in ("Admin", "HOD")
