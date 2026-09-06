from __future__ import annotations

import json
from typing import Any


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> bool:
        return False
