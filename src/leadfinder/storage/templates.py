"""User-created pitch templates."""

from __future__ import annotations

import sqlite3

from leadfinder.errors import TemplateError
from leadfinder.templates import PitchTemplate
from leadfinder.workflow import to_iso, utc_now


class TemplatesMixin:
    _conn: sqlite3.Connection

    def create_template(
        self,
        *,
        name: str,
        body: str,
        business_type: str = "",
        presence_type: str = "",
        language: str = "",
        commit: bool = True,
    ) -> PitchTemplate:
        stamp = to_iso(utc_now())
        title = name.strip()
        if not title:
            raise TemplateError("Template name is required.")
        cursor = self._conn.execute(
            """
            INSERT INTO pitch_templates (
                name, body, created_at, updated_at, business_type, presence_type, language
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (title, body, stamp, stamp, business_type, presence_type, language),
        )
        if commit:
            self._conn.commit()
        found = self.get_template(int(cursor.lastrowid or 0))
        assert found is not None
        return found

    def get_template(self, template_id: int) -> PitchTemplate | None:
        row = self._conn.execute(
            "SELECT * FROM pitch_templates WHERE id = ?",
            (template_id,),
        ).fetchone()
        return _row_to_template(row) if row else None

    def list_templates(self) -> list[PitchTemplate]:
        cursor = self._conn.execute(
            "SELECT * FROM pitch_templates ORDER BY name COLLATE NOCASE, id"
        )
        return [_row_to_template(row) for row in cursor.fetchall()]

    def update_template(
        self,
        template_id: int,
        *,
        name: str | None = None,
        body: str | None = None,
        business_type: str | None = None,
        presence_type: str | None = None,
        language: str | None = None,
    ) -> PitchTemplate:
        current = self.get_template(template_id)
        if current is None:
            raise TemplateError(f"Unknown template: {template_id}")
        stamp = to_iso(utc_now())
        self._conn.execute(
            """
            UPDATE pitch_templates SET
                name = ?, body = ?, updated_at = ?, business_type = ?,
                presence_type = ?, language = ?
            WHERE id = ?
            """,
            (
                current.name if name is None else name.strip() or current.name,
                current.body if body is None else body,
                stamp,
                current.business_type if business_type is None else business_type,
                current.presence_type if presence_type is None else presence_type,
                current.language if language is None else language,
                template_id,
            ),
        )
        self._conn.commit()
        found = self.get_template(template_id)
        assert found is not None
        return found

    def delete_template(self, template_id: int) -> None:
        self._conn.execute("DELETE FROM pitch_templates WHERE id = ?", (template_id,))
        self._conn.commit()


def _row_to_template(row: sqlite3.Row) -> PitchTemplate:
    return PitchTemplate(
        id=int(row["id"]),
        name=row["name"],
        body=row["body"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        business_type=row["business_type"],
        presence_type=row["presence_type"],
        language=row["language"],
    )
