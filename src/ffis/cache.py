"""
SQLite-backed identification cache.

Cache key: SHA-256 of file content (FFIS non-normative guidance:
"cache identification results based on file checksums to avoid
re-processing identical files").

Results are stored as JSON and deserialized on hit.
"""

import json
from typing import Optional

import aiosqlite

from .models.identification import IdentificationResult


class IdentificationCache:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._ready = False

    async def setup(self) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    sha256      TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    cached_at   TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            await db.commit()
        self._ready = True

    async def get(self, sha256: str) -> Optional[IdentificationResult]:
        if not self._ready:
            return None
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT result_json FROM cache WHERE sha256 = ?", (sha256,)
            ) as cursor:
                row = await cursor.fetchone()
        if row is None:
            return None
        result = IdentificationResult.model_validate_json(row[0])
        result.cached = True
        return result

    async def set(self, sha256: str, result: IdentificationResult) -> None:
        if not self._ready:
            return
        payload = result.model_dump_json()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO cache (sha256, result_json) VALUES (?, ?)",
                (sha256, payload),
            )
            await db.commit()
