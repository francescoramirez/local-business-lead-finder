"""Desktop application identity. Keep QSettings org/app names stable."""

from __future__ import annotations

from typing import Any

from leadfinder import __version__

APP_DISPLAY_NAME = "LeadFinder"
ORGANIZATION_NAME = "LeadFinder"
ORGANIZATION_DOMAIN = "leadfinder.local"
PRODUCT_NAME = "LeadFinder"
PUBLISHER = "FrancescoRamirezC"
REPOSITORY_URL = "https://github.com/francescoramirez/local-business-lead-finder"
LICENSE_NAME = "MIT License"


def application_version() -> str:
    return __version__


def apply_qt_identity(app: Any) -> None:
    """Set Qt application identity without changing QSettings org/app names."""
    setter_name = getattr(app, "setApplicationName", None)
    if callable(setter_name):
        app.setApplicationName(APP_DISPLAY_NAME)
    setter_org = getattr(app, "setOrganizationName", None)
    if callable(setter_org):
        app.setOrganizationName(ORGANIZATION_NAME)
    setter_domain = getattr(app, "setOrganizationDomain", None)
    if callable(setter_domain):
        app.setOrganizationDomain(ORGANIZATION_DOMAIN)
    setter_version = getattr(app, "setApplicationVersion", None)
    if callable(setter_version):
        app.setApplicationVersion(application_version())
