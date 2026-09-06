"""Optional AI sales-prep helpers. Discovery and scoring do not require AI."""

from leadfinder.ai.models import SalesPrepRequest, SalesPrepResult
from leadfinder.ai.provider import ai_configured, groq_model

__all__ = [
    "SalesPrepRequest",
    "SalesPrepResult",
    "ai_configured",
    "groq_model",
]
