"""PyInstaller GUI entry. No console CLI."""

from __future__ import annotations

from leadfinder.desktop.packaged_checks import run_if_requested
from leadfinder.gui.app import run_gui


def main() -> None:
    packaged = run_if_requested()
    if packaged is not None:
        raise SystemExit(packaged)
    raise SystemExit(run_gui())


if __name__ == "__main__":
    main()
