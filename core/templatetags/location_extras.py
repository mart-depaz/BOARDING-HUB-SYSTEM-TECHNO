# core app templatestags/location_extras.py

from django import template
import json
import ast

register = template.Library()

@register.filter
def format_location(value):
    """Format a location value into a readable single-line string.

    Accepts:
    - dict-like objects with keys: province/state, city, barangay, address/display_name
    - JSON stringified dicts
    - Python-literal dict strings
    - plain strings (returned as-is)
    """
    if not value:
        return ''
    # If it's a dict-like object
    if isinstance(value, dict):
        parts = [value.get('province') or value.get('state') or '', value.get('city') or '', value.get('barangay') or '', value.get('address') or value.get('display_name') or '']
        return ', '.join([p for p in parts if p and str(p).strip()])

    # If string, try to parse JSON or Python literal
    if isinstance(value, str):
        s = value.strip()
        # Try JSON
        try:
            parsed = json.loads(s)
        except Exception:
            try:
                parsed = ast.literal_eval(s)
            except Exception:
                parsed = None
        if isinstance(parsed, dict):
            parts = [parsed.get('province') or parsed.get('state') or '', parsed.get('city') or '', parsed.get('barangay') or '', parsed.get('address') or parsed.get('display_name') or '']
            return ', '.join([p for p in parts if p and str(p).strip()])
        # Not a dict-like string -- return as-is
        return s

    # Fallback
    return str(value)


@register.filter
def to_json(value):
    """Serialize Python data to a JSON string."""
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return json.dumps([])