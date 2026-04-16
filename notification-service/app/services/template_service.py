import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class SafeDict(dict):
    """Prevents KeyError by returning the key wrapped in brackets if missing."""
    def __missing__(self, key):
        return f"[{key}]"

class TemplateService:
    @staticmethod
    def render_body(template_str: str, payload: Dict[str, Any]) -> str:
        """
        Render a template body using the provided payload.
        Uses SafeDict to prevent crashing on missing dynamic fields (AS-02).
        """
        if not template_str:
            return ""
        try:
            return template_str.format_map(SafeDict(payload))
        except Exception as e:
            logger.error(f"Error rendering template body: {e}")
            return template_str

    @staticmethod
    def render_subject(subject_str: str, payload: Dict[str, Any]) -> str:
        """
        Render a template subject with safety checks.
        """
        if not subject_str:
            return ""
        try:
            return subject_str.format_map(SafeDict(payload))
        except Exception as e:
            logger.error(f"Error rendering subject: {e}")
            return subject_str
