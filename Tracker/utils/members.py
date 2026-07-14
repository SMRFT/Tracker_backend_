import json


def parse_members(members_raw):
    """
    Card.members is stored inconsistently as either a JSON string or a list.
    Normalize it to a list, tolerating malformed/empty input.
    """
    if not members_raw:
        return []
    try:
        return json.loads(members_raw) if isinstance(members_raw, str) else members_raw
    except Exception:
        return []


def is_employee_in_members(members_raw, employee_id):
    if not employee_id:
        return False
    members = parse_members(members_raw)
    return any(str(m.get("employeeId")) == str(employee_id) for m in members)
