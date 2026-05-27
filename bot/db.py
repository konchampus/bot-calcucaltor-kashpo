from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite


@dataclass(slots=True)
class PaginationResult:
    items: list[dict[str, Any]]
    total: int


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.conn = await aiosqlite.connect(self.path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON;")
        await self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                value REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                rack_length REAL NOT NULL,
                rattan_width REAL NOT NULL,
                basket_diameter REAL NOT NULL,
                harness_count INTEGER NOT NULL,
                base_result REAL NOT NULL,
                final_result REAL NOT NULL,
                comment TEXT,
                leftovers_note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS calculation_patterns (
                calculation_id INTEGER NOT NULL,
                pattern_id INTEGER NOT NULL,
                PRIMARY KEY (calculation_id, pattern_id),
                FOREIGN KEY (calculation_id) REFERENCES calculations(id) ON DELETE CASCADE,
                FOREIGN KEY (pattern_id) REFERENCES patterns(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS saved_calculations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                calculation_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (user_id, calculation_id),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (calculation_id) REFERENCES calculations(id) ON DELETE CASCADE
            );
            """
        )
        await self.conn.commit()

    async def close(self) -> None:
        if self.conn is not None:
            await self.conn.close()
            self.conn = None

    async def _ensure_user(self, telegram_id: int) -> int:
        assert self.conn is not None
        await self.conn.execute(
            "INSERT OR IGNORE INTO users (telegram_id) VALUES (?)",
            (telegram_id,),
        )
        await self.conn.commit()
        cursor = await self.conn.execute(
            "SELECT id FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()
        return int(row["id"])

    async def add_pattern(self, telegram_id: int, name: str, value: float) -> int:
        assert self.conn is not None
        user_id = await self._ensure_user(telegram_id)
        cursor = await self.conn.execute(
            "INSERT INTO patterns (user_id, name, value) VALUES (?, ?, ?)",
            (user_id, name, value),
        )
        await self.conn.commit()
        return int(cursor.lastrowid)

    async def list_patterns(self, telegram_id: int) -> list[dict[str, Any]]:
        assert self.conn is not None
        user_id = await self._ensure_user(telegram_id)
        cursor = await self.conn.execute(
            "SELECT id, name, value FROM patterns WHERE user_id = ? ORDER BY id DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def delete_pattern(self, telegram_id: int, pattern_id: int) -> bool:
        assert self.conn is not None
        user_id = await self._ensure_user(telegram_id)
        cursor = await self.conn.execute(
            "DELETE FROM patterns WHERE user_id = ? AND id = ?",
            (user_id, pattern_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def create_calculation(
        self,
        telegram_id: int,
        rack_length: float,
        rattan_width: float,
        basket_diameter: float,
        harness_count: int,
        base_result: float,
        final_result: float,
        pattern_ids: list[int],
    ) -> int:
        assert self.conn is not None
        user_id = await self._ensure_user(telegram_id)

        cursor = await self.conn.execute(
            """
            INSERT INTO calculations (
                user_id,
                rack_length,
                rattan_width,
                basket_diameter,
                harness_count,
                base_result,
                final_result
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                rack_length,
                rattan_width,
                basket_diameter,
                harness_count,
                base_result,
                final_result,
            ),
        )
        calculation_id = int(cursor.lastrowid)

        if pattern_ids:
            placeholder = ",".join("?" for _ in pattern_ids)
            valid_cursor = await self.conn.execute(
                f"SELECT id FROM patterns WHERE user_id = ? AND id IN ({placeholder})",
                (user_id, *pattern_ids),
            )
            valid_rows = await valid_cursor.fetchall()
            valid_ids = [int(row["id"]) for row in valid_rows]
            await self.conn.executemany(
                "INSERT OR IGNORE INTO calculation_patterns (calculation_id, pattern_id) VALUES (?, ?)",
                [(calculation_id, pattern_id) for pattern_id in valid_ids],
            )

        await self.conn.commit()
        return calculation_id

    async def list_calculations(
        self,
        telegram_id: int,
        page: int,
        per_page: int,
    ) -> PaginationResult:
        assert self.conn is not None
        user_id = await self._ensure_user(telegram_id)
        offset = (page - 1) * per_page

        total_cursor = await self.conn.execute(
            "SELECT COUNT(*) AS total FROM calculations WHERE user_id = ?",
            (user_id,),
        )
        total_row = await total_cursor.fetchone()
        total = int(total_row["total"])

        cursor = await self.conn.execute(
            """
            SELECT id, final_result, created_at
            FROM calculations
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, per_page, offset),
        )
        rows = await cursor.fetchall()
        return PaginationResult(items=[dict(row) for row in rows], total=total)

    async def get_calculation(self, telegram_id: int, calculation_id: int) -> dict[str, Any] | None:
        assert self.conn is not None
        user_id = await self._ensure_user(telegram_id)
        cursor = await self.conn.execute(
            """
            SELECT id, rack_length, rattan_width, basket_diameter, harness_count,
                   base_result, final_result, comment, leftovers_note, created_at
            FROM calculations
            WHERE user_id = ? AND id = ?
            """,
            (user_id, calculation_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        result = dict(row)
        patterns_cursor = await self.conn.execute(
            """
            SELECT p.id, p.name, p.value
            FROM patterns p
            JOIN calculation_patterns cp ON cp.pattern_id = p.id
            WHERE cp.calculation_id = ?
            ORDER BY p.id DESC
            """,
            (calculation_id,),
        )
        pattern_rows = await patterns_cursor.fetchall()
        result["patterns"] = [dict(item) for item in pattern_rows]
        return result

    async def update_calculation_notes(
        self,
        telegram_id: int,
        calculation_id: int,
        comment: str,
        leftovers_note: str | None,
    ) -> bool:
        assert self.conn is not None
        user_id = await self._ensure_user(telegram_id)
        cursor = await self.conn.execute(
            """
            UPDATE calculations
            SET comment = ?, leftovers_note = ?
            WHERE id = ? AND user_id = ?
            """,
            (comment, leftovers_note, calculation_id, user_id),
        )
        await self.conn.commit()
        return cursor.rowcount > 0

    async def save_calculation(self, telegram_id: int, calculation_id: int, title: str) -> bool:
        assert self.conn is not None
        user_id = await self._ensure_user(telegram_id)

        calc_cursor = await self.conn.execute(
            "SELECT id FROM calculations WHERE id = ? AND user_id = ?",
            (calculation_id, user_id),
        )
        calculation = await calc_cursor.fetchone()
        if calculation is None:
            return False

        await self.conn.execute(
            """
            INSERT INTO saved_calculations (user_id, calculation_id, title)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, calculation_id)
            DO UPDATE SET title = excluded.title
            """,
            (user_id, calculation_id, title),
        )
        await self.conn.commit()
        return True

    async def list_saved_calculations(
        self,
        telegram_id: int,
        page: int,
        per_page: int,
    ) -> PaginationResult:
        assert self.conn is not None
        user_id = await self._ensure_user(telegram_id)
        offset = (page - 1) * per_page

        total_cursor = await self.conn.execute(
            "SELECT COUNT(*) AS total FROM saved_calculations WHERE user_id = ?",
            (user_id,),
        )
        total_row = await total_cursor.fetchone()
        total = int(total_row["total"])

        cursor = await self.conn.execute(
            """
            SELECT s.id AS saved_id, s.title, s.created_at AS saved_at,
                   c.id AS calculation_id, c.final_result
            FROM saved_calculations s
            JOIN calculations c ON c.id = s.calculation_id
            WHERE s.user_id = ?
            ORDER BY s.id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, per_page, offset),
        )
        rows = await cursor.fetchall()
        return PaginationResult(items=[dict(row) for row in rows], total=total)
