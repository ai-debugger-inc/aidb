#!/usr/bin/env python3
"""Validate skill-rules.json against JSON schema."""

import json
import sys
from pathlib import Path

try:
    import jsonschema
except ImportError:
    print("ERROR: jsonschema not installed. Run: pip install jsonschema")
    sys.exit(1)


def validate_skill_rules() -> bool:
    """Validate skill-rules.json against its schema."""
    repo_root = Path(__file__).parent.parent.parent
    rules_file = repo_root / ".claude" / "skills" / "skill-rules.json"
    schema_file = repo_root / ".claude" / "skills" / "skill-rules.schema.json"

    if not rules_file.exists():
        print(f"ERROR: {rules_file} not found")
        return False

    if not schema_file.exists():
        print(f"ERROR: {schema_file} not found")
        return False

    with open(schema_file) as f:
        schema = json.load(f)

    with open(rules_file) as f:
        rules = json.load(f)

    try:
        jsonschema.validate(instance=rules, schema=schema)
        print("✅ skill-rules.json is valid")
        return True
    except jsonschema.ValidationError as e:
        print(f"❌ skill-rules.json validation failed:\n{e.message}")
        print(f"\nPath: {' -> '.join(str(p) for p in e.path)}")
        return False
    except jsonschema.SchemaError as e:
        print(f"❌ Schema itself is invalid:\n{e.message}")
        return False


if __name__ == "__main__":
    sys.exit(0 if validate_skill_rules() else 1)
