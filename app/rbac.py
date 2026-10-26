"""Single source of truth for access rules.

A chunk is readable by a user only when ALL of these hold:
  1. the user's role is in the document's allowed_roles
  2. the document's sensitivity <= the role's clearance
  3. the document belongs to the user's department (or is company-wide "all")
Admins bypass (3) but still obey (1) and (2) -- admin is always in allowed_roles.
"""
from typing import Any

ROLES = ("admin", "manager", "employee")
SENSITIVITY = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
CLEARANCE = {"employee": 1, "manager": 2, "admin": 3}
COMPANY_WIDE = "all"


def sensitivity_rank(level: str) -> int:
    if level not in SENSITIVITY:
        raise ValueError(f"Unknown sensitivity '{level}'")
    return SENSITIVITY[level]


def chroma_filter(user: dict) -> dict[str, Any]:
    """Filter applied INSIDE the vector search (pre-filter, not post-filter)."""
    role = user["role"]
    conditions: list[dict] = [
        {f"role_{role}": True},
        {"sensitivity_rank": {"$lte": CLEARANCE[role]}},
    ]
    if role != "admin":
        conditions.append({"department": {"$in": [user["department"], COMPANY_WIDE]}})
    return {"$and": conditions}


def can_access(user: dict, doc: dict) -> bool:
    """Python mirror of chroma_filter, used for listing/deleting documents."""
    role = user["role"]
    if role not in doc["allowed_roles"]:
        return False
    if sensitivity_rank(doc["sensitivity"]) > CLEARANCE[role]:
        return False
    if role != "admin" and doc["department"] not in (user["department"], COMPANY_WIDE):
        return False
    return True


def can_upload(user: dict, department: str, sensitivity: str) -> bool:
    if user["role"] == "admin":
        return True
    if user["role"] == "manager":
        return (
            department == user["department"]
            and sensitivity_rank(sensitivity) <= CLEARANCE["manager"]
        )
    return False
