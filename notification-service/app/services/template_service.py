import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TemplateService:
    @staticmethod
    def render_body(template_str: str, payload: Dict[str, Any]) -> str:
        """
        Render a template body using the provided payload.
        Uses str.format_map() for interpolation.
        """
        try:
            return template_str.format_map(payload)
        except KeyError as e:
            logger.error(f"Missing placeholder in template payload: {e}")
            # Fallback: keep the placeholder or return partially rendered
            return template_str
        except Exception as e:
            logger.error(f"Error rendering template: {e}")
            return template_str

    @staticmethod
    def render_subject(subject_str: str, payload: Dict[str, Any]) -> str:
        """
        Render a template subject if it contains placeholders.
        """
        if not subject_str:
            return ""
        try:
            return subject_str.format_map(payload)
        except Exception:
            return subject_str
