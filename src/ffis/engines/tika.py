"""
Apache Tika identification engine (optional).

Tika provides broad coverage of scientific and rich-media formats not always
present in PRONOM.  It requires either:
  - A running Tika REST server (FFIS_TIKA_SERVER_URL), or
  - The `tika` Python package which auto-starts a local Java server.

This engine is disabled by default (FFIS_TIKA_ENABLED=false) to avoid
introducing a Java dependency in minimal deployments.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Optional

import httpx

from ..models.identification import Identifier, IdentificationMethod, ToolResult
from .base import BaseEngine


class TikaEngine(BaseEngine):
    name = "tika"

    def __init__(self, server_url: Optional[str] = None) -> None:
        self._server_url = server_url

    async def identify_bytes(self, content: bytes, filename: Optional[str] = None) -> ToolResult:
        suffix = Path(filename).suffix if filename else ""
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(content)
            tmp.flush()
            return await self.identify_path(tmp.name)

    async def identify_path(self, path: str) -> ToolResult:
        if self._server_url:
            return await self._identify_via_rest(path)
        return await asyncio.get_event_loop().run_in_executor(None, self._identify_via_library, path)

    async def is_available(self) -> bool:
        if self._server_url:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(self._server_url)
                    return r.status_code < 500
            except Exception:
                return False
        try:
            import tika  # type: ignore[import]  # noqa: F401
            return True
        except ImportError:
            return False

    async def get_version(self) -> Optional[str]:
        if self._server_url:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(f"{self._server_url}/version")
                    return r.text.strip()
            except Exception:
                return None
        return None

    async def _identify_via_rest(self, path: str) -> ToolResult:
        try:
            with open(path, "rb") as fh:
                content = fh.read()
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.put(
                    f"{self._server_url}/detect/stream",
                    content=content,
                    headers={"Accept": "text/plain"},
                )
                r.raise_for_status()
                mime = r.text.strip()
            identifiers = [Identifier(value=mime, scheme="MIME")] if mime else []
            return ToolResult(
                name=self.name,
                identifiers=identifiers,
                method=IdentificationMethod.MIME_MAGIC,
                raw_output={"mime": mime},
            )
        except Exception as exc:
            return ToolResult(name=self.name, error=str(exc))

    def _identify_via_library(self, path: str) -> ToolResult:
        try:
            from tika import detect  # type: ignore[import]
            mime = detect.from_file(path)
            identifiers = [Identifier(value=mime, scheme="MIME")] if mime else []
            return ToolResult(
                name=self.name,
                identifiers=identifiers,
                method=IdentificationMethod.MIME_MAGIC,
                raw_output={"mime": mime},
            )
        except Exception as exc:
            return ToolResult(name=self.name, error=str(exc))
