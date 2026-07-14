import logging
from .db import get_global_db

logger = logging.getLogger(__name__)

def get_employee_names_by_ids(employee_ids):
    """
    Batch-resolve employeeName for a collection of employee ids in a single query,
    avoiding one get_employee_name_by_id() query per row.
    Returns a dict keyed by the string form of the employee id.
    """
    ids = {str(eid) for eid in employee_ids if eid}
    if not ids:
        return {}
    try:
        db = get_global_db()
        profiles = db["backend_diagnostics_profile"]
        employee_profiles = list(profiles.find(
            {"employeeId": {"$in": list(ids)}},
            {"employeeId": 1, "employeeName": 1, "_id": 0}
        ))
        return {str(p["employeeId"]): p.get("employeeName") for p in employee_profiles}
    except Exception as e:
        logger.error(f"get_employee_names_by_ids failed for {ids}: {e}")
        return {}

def get_employee_name_by_id(employee_id):
    """
    Fetch employeeName from MongoDB 'backend_diagnostics_profile' in the Global database,
    supporting both string and integer matching.
    """
    if not employee_id:
        return None
    try:
        db = get_global_db()
        profiles = db["backend_diagnostics_profile"]
        
        # Try matching string and integer representation (e.g. "123" vs 123)
        query_conditions = [{"employeeId": str(employee_id)}]
        if str(employee_id).isdigit():
            query_conditions.append({"employeeId": int(employee_id)})

        query = {"$or": query_conditions}
        profile = profiles.find_one(query, {"employeeName": 1, "_id": 0})
        
        return profile.get("employeeName") if profile else None
    except Exception as e:
        logger.error(f"get_employee_name_by_id failed for {employee_id}: {e}")
        return None
