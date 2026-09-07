"""SQLite store facade for user-generated lead metadata (not Places content)."""

from __future__ import annotations

from leadfinder.storage.activities import ActivitiesMixin
from leadfinder.storage.campaigns import CampaignsMixin
from leadfinder.storage.connection import ConnectionMixin, validate_leadfinder_db
from leadfinder.storage.experiments import ExperimentsMixin
from leadfinder.storage.leads import LeadsMixin
from leadfinder.storage.templates import TemplatesMixin
from leadfinder.storage.workspace import WorkspaceMixin

__all__ = ["LocalLeadStore", "validate_leadfinder_db"]


class LocalLeadStore(
    ConnectionMixin,
    LeadsMixin,
    ActivitiesMixin,
    CampaignsMixin,
    ExperimentsMixin,
    TemplatesMixin,
    WorkspaceMixin,
):
    """Public storage API used by LeadService, CLI, and GUI."""
