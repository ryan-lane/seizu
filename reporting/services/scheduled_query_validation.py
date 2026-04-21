"""Shared validation helpers for scheduled query create/update flows."""
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from reporting import scheduled_query_modules


def validate_action_configs(actions: List[Dict[str, Any]]) -> Optional[str]:
    """Validate each action's config against the module's declared schema.

    Returns an error message string if validation fails, or None if valid.
    """
    schemas = scheduled_query_modules.get_action_schemas()
    for action in actions:
        action_type = action.get("action_type", "")
        action_config = action.get("action_config", {})
        if action_type not in schemas:
            return (
                f"Unknown action type '{action_type}'. Valid types: {sorted(schemas)}."
            )
        for field in schemas[action_type]:
            if not field.required:
                continue
            value = action_config.get(field.name)
            if value is None or value == "" or value == []:
                return (
                    f"Action type '{action_type}' is missing required field "
                    f"'{field.name}'."
                )
    return None
