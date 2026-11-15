"""
ReliefOps AI — Security & Input Validation Utilities
Implements strict parameter sanitization, schema validation, path traversal prevention,
and bounds-checking for disaster context payloads and user inputs.

Academic Disclaimer:
Developed exclusively for CSE476 (Agentic AI and Intelligent Automation).
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


VALID_HAZARDS = {"FLOOD", "EARTHQUAKE", "CYCLONE", "LANDSLIDE"}
VALID_SEVERITIES = {"MODERATE", "SEVERE", "CATASTROPHIC"}
VALID_ACCESS_STATUSES = {"OPEN", "DEGRADED", "BLOCKED", "AIR_ONLY"}
IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_\-]+$")


class SecurityValidationError(ValueError):
    """Raised when an untrusted input fails validation checks."""
    pass


def sanitize_identifier(value: Any, default: str = "UNKNOWN", max_len: int = 64) -> str:
    """
    Sanitizes an alphanumeric identifier (e.g. event_id, zone_id, plan_id) to prevent injection.
    """
    if value is None:
        return default
    clean = str(value).strip()
    if not clean:
        return default
    if not IDENTIFIER_REGEX.match(clean):
        # Strip illegal characters
        clean = re.sub(r"[^a-zA-Z0-9_\-]", "", clean)
    return clean[:max_len] if clean else default


def validate_path_safety(file_path: Union[str, Path], allowed_parent_dir: Union[str, Path]) -> Path:
    """
    Guarantees that a resolved file path strictly resides within the allowed parent directory,
    preventing arbitrary path traversal vulnerabilities.
    """
    target = Path(file_path).resolve()
    parent = Path(allowed_parent_dir).resolve()

    try:
        target.relative_to(parent)
    except ValueError:
        raise SecurityValidationError(f"Path traversal detected: {target} is outside {parent}")

    return target


def validate_zone_payload(zone: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates a single affected zone dictionary against physical and geospatial bounds.
    """
    errors: List[str] = []
    if not isinstance(zone, dict):
        return False, ["Zone payload must be a dictionary"]

    # Zone ID
    zid = str(zone.get("zone_id") or zone.get("id") or "").strip()
    if not zid:
        errors.append("Zone missing required identifier 'zone_id'")
    elif not IDENTIFIER_REGEX.match(zid):
        errors.append(f"Invalid characters in zone_id: '{zid}'")

    # Population
    try:
        pop = int(zone.get("population") if zone.get("population") is not None else zone.get("affected_population", 0))
        if pop <= 0:
            errors.append(f"Population must be > 0 (received {pop})")
    except (ValueError, TypeError):
        errors.append("Population must be a valid integer")

    # Damage Level (1-5)
    try:
        dmg = int(zone.get("damage_level", 3))
        if dmg < 1 or dmg > 5:
            errors.append(f"Damage level must be between 1 and 5 (received {dmg})")
    except (ValueError, TypeError):
        errors.append("Damage level must be an integer between 1 and 5")

    # Vulnerability Index (0.0 - 1.0)
    try:
        vuln = float(zone.get("vulnerability_index", 0.5))
        if vuln < 0.0 or vuln > 1.0:
            errors.append(f"Vulnerability index must be in [0.0, 1.0] (received {vuln})")
    except (ValueError, TypeError):
        errors.append("Vulnerability index must be a float between 0.0 and 1.0")

    # Medical Urgency (0.0 - 1.0)
    try:
        med = float(zone.get("medical_urgency", 0.5))
        if med < 0.0 or med > 1.0:
            errors.append(f"Medical urgency must be in [0.0, 1.0] (received {med})")
    except (ValueError, TypeError):
        errors.append("Medical urgency must be a float between 0.0 and 1.0")

    # Access Status
    access = str(zone.get("access_status") or zone.get("road_status") or "OPEN").strip().upper()
    if access not in VALID_ACCESS_STATUSES:
        errors.append(f"Access status '{access}' must be one of {sorted(VALID_ACCESS_STATUSES)}")

    # Latitude (-90 to 90)
    try:
        lat = float(zone.get("latitude") if zone.get("latitude") is not None else zone.get("lat", 0.0))
        if lat < -90.0 or lat > 90.0:
            errors.append(f"Latitude must be in [-90.0, 90.0] (received {lat})")
    except (ValueError, TypeError):
        errors.append("Latitude must be a valid numeric coordinate")

    # Longitude (-180 to 180)
    try:
        lon = float(zone.get("longitude") if zone.get("longitude") is not None else zone.get("lon", 0.0))
        if lon < -180.0 or lon > 180.0:
            errors.append(f"Longitude must be in [-180.0, 180.0] (received {lon})")
    except (ValueError, TypeError):
        errors.append("Longitude must be a valid numeric coordinate")

    return (len(errors) == 0, errors)


def validate_disaster_context(context: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validates a complete disaster scenario context payload before execution.
    """
    errors: List[str] = []
    if not isinstance(context, dict):
        return False, ["Disaster context must be a dictionary"]

    # Hazard Type
    hazard = str(context.get("disaster_type", "")).strip().upper()
    if not hazard:
        errors.append("Missing required 'disaster_type'")
    elif hazard not in VALID_HAZARDS:
        errors.append(f"Invalid disaster_type '{hazard}'. Supported: {sorted(VALID_HAZARDS)}")

    # Severity Level
    raw_sev = str(context.get("severity_level") or context.get("severity") or "").strip().upper()
    if raw_sev and raw_sev not in VALID_SEVERITIES:
        # Check if Level 1-5 format
        if not re.match(r"^LEVEL\s*[1-5]", raw_sev):
            errors.append(f"Invalid severity '{raw_sev}'. Supported: {sorted(VALID_SEVERITIES)} or Level 1-5")

    # Planning Days
    try:
        days = int(context.get("planning_days", 3))
        if days < 1 or days > 30:
            errors.append(f"Planning days must be between 1 and 30 (received {days})")
    except (ValueError, TypeError):
        errors.append("Planning days must be an integer between 1 and 30")

    # Zones List
    zones = context.get("zones")
    if zones is None or not isinstance(zones, list):
        errors.append("Context must contain a non-empty 'zones' list")
    elif len(zones) == 0:
        errors.append("Context contains 0 zones (at least 1 required for allocation)")
    else:
        for idx, z in enumerate(zones):
            valid, z_errs = validate_zone_payload(z)
            if not valid:
                errors.extend([f"Zone {idx} ({z.get('zone_id', 'unknown')}): {e}" for e in z_errs])

    return (len(errors) == 0, errors)
