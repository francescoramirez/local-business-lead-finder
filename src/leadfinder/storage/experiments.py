"""Local experiments."""

from __future__ import annotations

import sqlite3

from leadfinder.errors import WorkspaceError
from leadfinder.models import Experiment
from leadfinder.storage.mapping import row_to_experiment
from leadfinder.workflow import to_iso, utc_now


class ExperimentsMixin:
    _conn: sqlite3.Connection

    def create_experiment(
        self,
        *,
        name: str,
        hypothesis: str = "",
        status: str = "draft",
        business_preset: str = "",
        location: str = "",
        digital_presence: str = "",
        opportunity_level: str = "",
        target_metric: str = "contact_to_interest",
        notes: str = "",
        observations: str = "",
        conclusion: str = "",
        created_at: str | None = None,
        commit: bool = True,
    ) -> Experiment:
        stamp = created_at or to_iso(utc_now())
        cursor = self._conn.execute(
            """
            INSERT INTO experiments (
                name, created_at, status, hypothesis, business_preset, location,
                digital_presence, opportunity_level, target_metric, notes,
                observations, conclusion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                stamp,
                status,
                hypothesis,
                business_preset,
                location,
                digital_presence,
                opportunity_level,
                target_metric,
                notes,
                observations,
                conclusion,
            ),
        )
        if commit:
            self._conn.commit()
        found = self.get_experiment(int(cursor.lastrowid or 0))
        assert found is not None
        return found

    def get_experiment(self, experiment_id: int) -> Experiment | None:
        row = self._conn.execute(
            "SELECT * FROM experiments WHERE id = ?",
            (experiment_id,),
        ).fetchone()
        if row is None:
            return None
        return self._experiment_from_row(row)

    def list_experiments(self) -> list[Experiment]:
        cursor = self._conn.execute(
            "SELECT * FROM experiments ORDER BY created_at DESC, id DESC"
        )
        return [self._experiment_from_row(row) for row in cursor.fetchall()]

    def update_experiment(
        self,
        experiment_id: int,
        *,
        name: str | None = None,
        status: str | None = None,
        hypothesis: str | None = None,
        notes: str | None = None,
        observations: str | None = None,
        conclusion: str | None = None,
        business_preset: str | None = None,
        location: str | None = None,
        digital_presence: str | None = None,
        opportunity_level: str | None = None,
    ) -> Experiment:
        current = self.get_experiment(experiment_id)
        if current is None:
            raise WorkspaceError(f"Unknown experiment: {experiment_id}")
        self._conn.execute(
            """
            UPDATE experiments SET
                name = ?, status = ?, hypothesis = ?, notes = ?,
                observations = ?, conclusion = ?, business_preset = ?,
                location = ?, digital_presence = ?, opportunity_level = ?
            WHERE id = ?
            """,
            (
                current.name if name is None else name,
                current.status if status is None else status,
                current.hypothesis if hypothesis is None else hypothesis,
                current.notes if notes is None else notes,
                current.observations if observations is None else observations,
                current.conclusion if conclusion is None else conclusion,
                current.business_preset if business_preset is None else business_preset,
                current.location if location is None else location,
                current.digital_presence if digital_presence is None else digital_presence,
                current.opportunity_level if opportunity_level is None else opportunity_level,
                experiment_id,
            ),
        )
        self._conn.commit()
        found = self.get_experiment(experiment_id)
        assert found is not None
        return found

    def attach_campaigns(
        self, experiment_id: int, campaign_ids: list[int], *, commit: bool = True
    ) -> None:
        for campaign_id in campaign_ids:
            if not campaign_id:
                continue
            self._conn.execute(
                """
                INSERT OR IGNORE INTO experiment_campaigns (experiment_id, campaign_id)
                VALUES (?, ?)
                """,
                (experiment_id, campaign_id),
            )
        if commit:
            self._conn.commit()

    def experiment_campaign_ids(self, experiment_id: int) -> frozenset[int]:
        rows = self._conn.execute(
            "SELECT campaign_id FROM experiment_campaigns WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchall()
        return frozenset(int(row["campaign_id"]) for row in rows)

    def _experiment_from_row(self, row: sqlite3.Row) -> Experiment:
        return row_to_experiment(
            row,
            tuple(sorted(self.experiment_campaign_ids(int(row["id"])))),
        )
