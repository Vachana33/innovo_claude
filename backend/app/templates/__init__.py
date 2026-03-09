"""
Template registry for document templates.

This module provides a registry that maps template_name to template functions.
Templates are Python modules that export a function returning a template structure.
"""

import logging
from typing import Dict, Callable, Any

logger = logging.getLogger(__name__)

# Template registry: maps template_name -> template function
TEMPLATE_REGISTRY: Dict[str, Callable[[], Dict[str, Any]]] = {}


def register_template(template_name: str, template_func: Callable[[], Dict[str, Any]]) -> None:
    """
    Register a template function in the registry.

    Args:
        template_name: Unique identifier for the template (e.g., "wtt_v1")
        template_func: Function that returns the template structure
    """
    TEMPLATE_REGISTRY[template_name] = template_func


def get_template(template_name: str) -> Dict[str, Any]:
    """
    Get a template by name from the registry.

    Args:
        template_name: The name of the template to retrieve

    Returns:
        Template structure dictionary with "sections" key

    Raises:
        KeyError: If template_name is not found in registry
        ValueError: If template function raises an exception or returns invalid structure
    """
    if template_name not in TEMPLATE_REGISTRY:
        raise KeyError(f"Template '{template_name}' not found in registry. Available templates: {list(TEMPLATE_REGISTRY.keys())}")

    try:
        template = TEMPLATE_REGISTRY[template_name]()
    except Exception as e:
        raise ValueError(f"Template function '{template_name}' raised an error: {str(e)}") from e

    # Validate template structure
    if not isinstance(template, dict):
        raise ValueError(f"Template '{template_name}' must return a dictionary, got {type(template)}")

    if "sections" not in template:
        raise ValueError(f"Template '{template_name}' must have a 'sections' key")

    if not isinstance(template["sections"], list):
        raise ValueError(f"Template '{template_name}' sections must be a list, got {type(template['sections'])}")

    # Validate each section has required fields
    for idx, section in enumerate(template["sections"]):
        if not isinstance(section, dict):
            raise ValueError(f"Template '{template_name}' section {idx} must be a dictionary")
        if "id" not in section:
            raise ValueError(f"Template '{template_name}' section {idx} is missing 'id' field")
        if "title" not in section:
            raise ValueError(f"Template '{template_name}' section {idx} is missing 'title' field")
        if "type" in section and section["type"] not in ["text", "milestone_table"]:
            raise ValueError(f"Template '{template_name}' section {section.get('id')} has invalid type: {section.get('type')}")

    return template


# Import templates to register them
# This ensures templates are registered when the module is imported
# Note: Import is after function definitions but before module execution
try:
    from .wtt_v1 import get_wtt_v1_template  # noqa: E402
    register_template("wtt_v1", get_wtt_v1_template)
    logger.info("Successfully registered template 'wtt_v1'")
except ImportError as e:
    # Template not yet created, will be registered when imported
    logger.warning(f"Template 'wtt_v1' could not be imported: {str(e)}")
except Exception as e:
    logger.error(f"Failed to register template 'wtt_v1': {str(e)}", exc_info=True)
