import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "library_system.settings")
django.setup()

from django.template import TemplateSyntaxError
from django.template.loader import get_template

try:
    template = get_template("students/owner_dashboard_students.html")
    print("✓ Template loaded successfully")
    print(
        "Template source file:",
        template.origin.name if hasattr(template, "origin") else "unknown",
    )
except TemplateSyntaxError as e:
    print("✗ Template Syntax Error:")
    print(f"  Error: {e}")
    print(
        f"  Line: {e.template_debug.get('line') if hasattr(e, 'template_debug') else 'unknown'}"
    )
    if hasattr(e, "template_debug") and e.template_debug:
        debug = e.template_debug
        print(f"  File: {debug.get('name', 'unknown')}")
        print(f"  Message: {debug.get('message', str(e))}")
        if "during" in debug:
            print(f"  During: {debug['during']}")
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    import traceback

    traceback.print_exc()
