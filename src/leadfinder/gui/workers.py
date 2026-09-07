from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from leadfinder.application.service import LeadService, friendly_error
from leadfinder.config import SearchConfig
from leadfinder.digital_presence import PresenceAnalyzer
from leadfinder.errors import LeadFinderError
from leadfinder.models import ManagedLead, SearchProgress
from leadfinder.places_client import PlacesClient

LOGGER = logging.getLogger("leadfinder")


def emit_failure(failed: Any, error: Exception) -> None:
    if isinstance(error, LeadFinderError):
        failed.emit(friendly_error(error))
        return
    LOGGER.exception("Unexpected worker error")
    failed.emit(friendly_error(error))


class SearchWorker(QThread):
    progressed = Signal(object)
    succeeded = Signal(object, object)
    failed = Signal(str)

    def __init__(
        self,
        service: LeadService,
        config: SearchConfig,
        *,
        client_factory: Callable[[], PlacesClient] | None = None,
        campaign_id: int | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._config = config
        self._client_factory = client_factory
        self._campaign_id = campaign_id
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            client = self._client_factory() if self._client_factory else None
            report, managed = self._service.search(
                self._config,
                client=client,
                on_progress=self._on_progress,
                is_cancelled=lambda: self._cancel,
                campaign_id=self._campaign_id,
            )
            self.succeeded.emit(report, managed)
        except Exception as error:  # noqa: BLE001
            emit_failure(self.failed, error)

    def _on_progress(self, event: SearchProgress) -> None:
        self.progressed.emit(event)


class AnalyzeWorker(QThread):
    progressed = Signal(object)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: LeadService,
        items: list[ManagedLead],
        *,
        analyzer: PresenceAnalyzer | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._items = items
        self._analyzer = analyzer
        self._cancel = False

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            updated = self._service.analyze_managed(
                self._items,
                analyzer=self._analyzer,
                on_progress=self._on_progress,
                is_cancelled=lambda: self._cancel,
            )
            self.succeeded.emit(updated)
        except Exception as error:  # noqa: BLE001
            emit_failure(self.failed, error)

    def _on_progress(self, event: SearchProgress) -> None:
        self.progressed.emit(event)


class SalesPrepWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: LeadService,
        item: ManagedLead,
        *,
        language: str,
        model: str = "",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._item = item
        self._language = language
        self._model = model

    def run(self) -> None:
        try:
            result = self._service.prepare_sales(
                self._item,
                language=self._language,
                model=self._model,
            )
            self.succeeded.emit(result)
        except Exception as error:  # noqa: BLE001
            emit_failure(self.failed, error)


class InsightsWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        service: LeadService,
        payload_source: object,
        *,
        language: str,
        experiment: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._source = payload_source
        self._language = language
        self._experiment = experiment

    def run(self) -> None:
        try:
            result = self._service.explain_insights(
                self._source,
                language=self._language,
                experiment=self._experiment,
            )
            self.succeeded.emit(result)
        except Exception as error:  # noqa: BLE001
            emit_failure(self.failed, error)
