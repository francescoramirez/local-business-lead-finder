from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from leadfinder.application.service import LeadService, friendly_error
from leadfinder.config import SearchConfig
from leadfinder.digital_presence import PresenceAnalyzer
from leadfinder.errors import LeadFinderError
from leadfinder.models import ManagedLead, SearchProgress
from leadfinder.places_client import PlacesClient


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
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._config = config
        self._client_factory = client_factory
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
            )
            self.succeeded.emit(report, managed)
        except LeadFinderError as error:
            self.failed.emit(friendly_error(error))
        except Exception as error:  # noqa: BLE001
            self.failed.emit(friendly_error(error))

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
        except LeadFinderError as error:
            self.failed.emit(friendly_error(error))
        except Exception as error:  # noqa: BLE001
            self.failed.emit(friendly_error(error))

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
        except LeadFinderError as error:
            self.failed.emit(friendly_error(error))
        except Exception as error:  # noqa: BLE001
            self.failed.emit(friendly_error(error))
