"""
Siegfried identification engine.

Supports two modes (FFIS-REQ-4-01):
  - Subprocess mode: invokes the local `sf` binary directly.
  - REST mode: calls a Siegfried sidecar server (FFIS_SIEGFRIED_SERVER_URL).

Siegfried is the recommended primary engine per the FFIS specification.
Registry coverage: PRONOM, MIME, Wikidata (via default.sig).
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Optional

import httpx

from ..models.identification import (
    Identifier,
    IdentificationMethod,
    ToolResult,
)
from .base import BaseEngine

# Maps Siegfried namespace names to our scheme labels
_NS_TO_SCHEME: dict[str, str] = {
    "pronom": "PRONOM",
    "mime": "MIME",
    "wikidata": "WIKIDATA",
    "tika": "MIME",
    "freedesktop": "MIME",
    "loc": "LOC",
}

_PRONOM_URI_PREFIX = "https://www.nationalarchives.gov.uk/pronom/"
_WIKIDATA_URI_PREFIX = "https://www.wikidata.org/wiki/"


def _parse_basis(basis_str: str) -> IdentificationMethod:
    if not basis_str:
        return IdentificationMethod.UNKNOWN
    b = basis_str.lower()
    if "container" in b:
        return IdentificationMethod.CONTAINER_SIGNATURE
    if "byte match" in b or "byte signature" in b or "signature" in b:
        return IdentificationMethod.BYTE_SIGNATURE
    if "xml" in b:
        return IdentificationMethod.XML_STRUCTURE
    if "extension" in b:
        return IdentificationMethod.EXTENSION
    return IdentificationMethod.UNKNOWN


def _build_uri(scheme: str, value: str) -> Optional[str]:
    if scheme == "PRONOM" and value and not value.startswith("UNKNOWN"):
        return f"{_PRONOM_URI_PREFIX}{value}"
    if scheme == "WIKIDATA" and value.startswith("Q"):
        return f"{_WIKIDATA_URI_PREFIX}{value}"
    return None


def _parse_sf_output(sf_json: dict, filename: Optional[str]) -> ToolResult:
    """Convert Siegfried JSON output into a ToolResult."""
    version = sf_json.get("siegfried", "unknown")
    files = sf_json.get("files", [])

    identifiers: list[Identifier] = []
    method = IdentificationMethod.UNKNOWN
    format_name: Optional[str] = None
    format_version: Optional[str] = None
    error: Optional[str] = None

    if files:
        file_entry = files[0]
        error = file_entry.get("errors") or None
        matches = file_entry.get("matches", [])

        for match in matches:
            ns = match.get("ns", "")
            scheme = _NS_TO_SCHEME.get(ns, ns.upper())
            value = match.get("id", "")

            if not value or value == "UNKNOWN":
                continue

            uri = _build_uri(scheme, value)
            identifiers.append(Identifier(value=value, scheme=scheme, uri=uri))

            # Also add MIME from the match if present and not already captured
            mime = match.get("mime", "")
            if mime and scheme != "MIME":
                if not any(i.value == mime and i.scheme == "MIME" for i in identifiers):
                    identifiers.append(Identifier(value=mime, scheme="MIME"))

            # Use the first match's basis and format info for the result
            if method == IdentificationMethod.UNKNOWN:
                method = _parse_basis(match.get("basis", ""))
            if format_name is None:
                format_name = match.get("format") or None
            if format_version is None:
                format_version = match.get("version") or None

    return ToolResult(
        name="siegfried",
        version=version,
        identifiers=identifiers,
        method=method,
        format_name=format_name,
        format_version=format_version,
        raw_output=sf_json,
        error=error,
    )


class SiegfriedEngine(BaseEngine):
    name = "siegfried"

    def __init__(self, binary: str = "sf", server_url: Optional[str] = None) -> None:
        self._binary = binary
        self._server_url = server_url

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def identify_bytes(self, content: bytes, filename: Optional[str] = None) -> ToolResult:
        suffix = Path(filename).suffix if filename else ""
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(content)
            tmp.flush()
            return await self.identify_path(tmp.name)

    async def identify_path(self, path: str) -> ToolResult:
        if self._server_url:
            return await self._identify_via_rest(path)
        return await self._identify_via_subprocess(path)

    async def is_available(self) -> bool:
        if self._server_url:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(self._server_url)
                    return r.status_code < 500
            except Exception:
                return False
        try:
            proc = await asyncio.create_subprocess_exec(
                self._binary, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            return proc.returncode == 0
        except FileNotFoundError:
            return False

    async def get_version(self) -> Optional[str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                self._binary, "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip().split("\n")[0]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _identify_via_subprocess(self, path: str) -> ToolResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                self._binary, "-json", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return ToolResult(
                    name=self.name,
                    error=stderr.decode().strip() or f"sf exited with code {proc.returncode}",
                )
            sf_json = json.loads(stdout)
            return _parse_sf_output(sf_json, path)
        except FileNotFoundError:
            return ToolResult(name=self.name, error="Siegfried binary not found")
        except Exception as exc:
            return ToolResult(name=self.name, error=str(exc))

    async def _identify_via_rest(self, path: str) -> ToolResult:
        """Call a Siegfried REST sidecar.

        Siegfried's server mode (`sf -serve host:port`) exposes a simple HTTP
        interface.  The path is passed as a query parameter so the sidecar reads
        directly from the shared volume — zero-copy as recommended by the spec.
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(
                    f"{self._server_url}/identify",
                    params={"format": "json", "name": path},
                )
                r.raise_for_status()
                return _parse_sf_output(r.json(), path)
        except Exception as exc:
            return ToolResult(name=self.name, error=str(exc))
