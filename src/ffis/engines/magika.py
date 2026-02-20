"""
Google Magika identification engine.

Used as a fallback for files that Siegfried cannot identify (returning
application/octet-stream or no match).  Magika uses a deep learning model
to infer content type from byte patterns without relying on magic number
databases, making it useful for novel or proprietary formats.

Per the spec: "Executables or binaries that fail standard identification
must be routed to Google Magika for AI-assisted identification."
"""

import asyncio
from typing import Optional

from ..models.identification import Identifier, IdentificationMethod, ToolResult
from .base import BaseEngine


class MagikaEngine(BaseEngine):
    name = "magika"

    def __init__(self) -> None:
        self._magika: Optional[object] = None

    def _get_magika(self) -> object:
        if self._magika is None:
            from magika import Magika  # type: ignore[import]
            self._magika = Magika()
        return self._magika

    async def identify_bytes(self, content: bytes, filename: Optional[str] = None) -> ToolResult:
        return await asyncio.get_event_loop().run_in_executor(
            None, self._run_on_bytes, content
        )

    async def identify_path(self, path: str) -> ToolResult:
        try:
            with open(path, "rb") as fh:
                content = fh.read()
        except OSError as exc:
            return ToolResult(name=self.name, error=str(exc))
        return await self.identify_bytes(content)

    async def is_available(self) -> bool:
        try:
            from magika import Magika  # type: ignore[import]  # noqa: F401
            return True
        except ImportError:
            return False

    async def get_version(self) -> Optional[str]:
        try:
            import magika  # type: ignore[import]
            return getattr(magika, "__version__", None)
        except ImportError:
            return None

    def _run_on_bytes(self, content: bytes) -> ToolResult:
        try:
            magika = self._get_magika()
            result = magika.identify_bytes(content)  # type: ignore[attr-defined]
            output = result.output

            identifiers: list[Identifier] = []
            mime = getattr(output, "mime_type", None)
            if mime:
                identifiers.append(Identifier(value=mime, scheme="MIME"))

            return ToolResult(
                name=self.name,
                version=None,
                identifiers=identifiers,
                method=IdentificationMethod.AI_PROBABILISTIC,
                format_name=getattr(output, "ct_label", None),
                raw_output={
                    "ct_label": getattr(output, "ct_label", None),
                    "mime_type": mime,
                    "score": getattr(output, "score", None),
                    "group": getattr(output, "group", None),
                },
            )
        except Exception as exc:
            return ToolResult(name=self.name, error=str(exc))
