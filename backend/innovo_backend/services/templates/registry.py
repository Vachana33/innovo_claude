"""Template registry for document templates."""
import logging
from typing import Dict, Callable, Any

logger = logging.getLogger(__name__)

TEMPLATE_REGISTRY: Dict[str, Callable[[], Dict[str, Any]]] = {}


def register_template(template_name: str, template_func: Callable[[], Dict[str, Any]]) -> None:
    TEMPLATE_REGISTRY[template_name] = template_func


def get_template(template_name: str) -> Dict[str, Any]:
    if template_name not in TEMPLATE_REGISTRY:
        raise KeyError(
            f"Template '{template_name}' not found in registry. "
            f"Available templates: {list(TEMPLATE_REGISTRY.keys())}"
        )

    try:
        template = TEMPLATE_REGISTRY[template_name]()
    except Exception as e:
        raise ValueError(f"Template function '{template_name}' raised an error: {str(e)}") from e

    if not isinstance(template, dict):
        raise ValueError(f"Template '{template_name}' must return a dictionary")
    if "sections" not in template:
        raise ValueError(f"Template '{template_name}' must have a 'sections' key")
    if not isinstance(template["sections"], list):
        raise ValueError(f"Template '{template_name}' sections must be a list")

    for idx, section in enumerate(template["sections"]):
        if not isinstance(section, dict):
            raise ValueError(f"Template '{template_name}' section {idx} must be a dictionary")
        if "id" not in section:
            raise ValueError(f"Template '{template_name}' section {idx} is missing 'id' field")
        if "title" not in section:
            raise ValueError(f"Template '{template_name}' section {idx} is missing 'title' field")
        if "type" in section and section["type"] not in ["text", "milestone_table"]:
            raise ValueError(
                f"Template '{template_name}' section {section.get('id')} has invalid type: {section.get('type')}"
            )

    return template


try:
    from innovo_backend.services.templates.wtt_v1 import get_wtt_v1_template  # noqa: E402
    register_template("wtt_v1", get_wtt_v1_template)
    logger.info("Successfully registered template 'wtt_v1'")
except ImportError as e:
    logger.warning(f"Template 'wtt_v1' could not be imported: {str(e)}")
except Exception as e:
    logger.error(f"Failed to register template 'wtt_v1': {str(e)}", exc_info=True)
