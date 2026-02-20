"""
Multi-engine orchestration and conflict resolution.

Implements FFIS-REQ-1-04, FFIS-REQ-3-01 through FFIS-REQ-3-04:

  1. Run all available engines concurrently.
  2. Collect all identifiers from all tool results.
  3. Apply deterministic conflict resolution to produce a single primary
     identifier using:
       a. Registry hierarchy (PRONOM > LOC > WIKIDATA > MIME)
       b. Method priority (byte signature > container > xml > ai > mime magic > extension)
       c. Specificity (prefer a named PUID over application/octet-stream)
  4. Emit warnings for extension mismatches and unidentified files.
"""

import asyncio
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import settings
from .engines.base import BaseEngine
from .models.identification import (
    IdentificationMethod,
    IdentificationOutcome,
    IdentificationResult,
    IdentificationWarning,
    Identifier,
    ProvenanceMetadata,
    ToolResult,
)

# Lower index = higher priority
_METHOD_PRIORITY: list[IdentificationMethod] = [
    IdentificationMethod.BYTE_SIGNATURE,
    IdentificationMethod.CONTAINER_SIGNATURE,
    IdentificationMethod.XML_STRUCTURE,
    IdentificationMethod.MIME_MAGIC,
    IdentificationMethod.AI_PROBABILISTIC,
    IdentificationMethod.EXTENSION,
    IdentificationMethod.UNKNOWN,
]

# Identifiers that represent "no useful identification"
_GENERIC_VALUES = {"application/octet-stream", "text/plain", "UNKNOWN"}


def _registry_rank(scheme: str, hierarchy: list[str]) -> int:
    try:
        return hierarchy.index(scheme.upper())
    except ValueError:
        return len(hierarchy)


def _method_rank(method: Optional[IdentificationMethod]) -> int:
    try:
        return _METHOD_PRIORITY.index(method)  # type: ignore[arg-type]
    except ValueError:
        return len(_METHOD_PRIORITY)


def _is_generic(identifier: Identifier) -> bool:
    return identifier.value in _GENERIC_VALUES


def _select_primary(
    tool_results: list[ToolResult],
    hierarchy: list[str],
) -> tuple[Optional[Identifier], Optional[IdentificationMethod]]:
    """
    Return the best (identifier, method) pair across all tool results.

    Selection order:
      1. Non-generic identifiers preferred over generic ones.
      2. Higher-priority registry (lower hierarchy index) wins.
      3. Higher-priority method wins.
    """
    candidates: list[tuple[Identifier, IdentificationMethod, int, int]] = []

    for result in tool_results:
        method_rank = _method_rank(result.method)
        for ident in result.identifiers:
            reg_rank = _registry_rank(ident.scheme, hierarchy)
            candidates.append((ident, result.method or IdentificationMethod.UNKNOWN, reg_rank, method_rank))

    if not candidates:
        return None, None

    # Separate non-generic from generic
    non_generic = [(i, m, rr, mr) for i, m, rr, mr in candidates if not _is_generic(i)]
    pool = non_generic if non_generic else candidates

    # Sort: registry rank asc, then method rank asc
    pool.sort(key=lambda x: (x[2], x[3]))
    best_ident, best_method, _, _ = pool[0]
    return best_ident, best_method


def _collect_all_identifiers(tool_results: list[ToolResult]) -> list[Identifier]:
    """Deduplicated union of all identifiers from all tools."""
    seen: set[tuple[str, str]] = set()
    out: list[Identifier] = []
    for result in tool_results:
        for ident in result.identifiers:
            key = (ident.scheme, ident.value)
            if key not in seen:
                seen.add(key)
                out.append(ident)
    return out


def _check_extension_mismatch(
    filename: Optional[str],
    primary: Optional[Identifier],
    tool_results: list[ToolResult],
) -> list[IdentificationWarning]:
    """
    Warn if the file extension does not match known extensions for the
    identified format (FFIS-REQ-3-04).

    The raw Siegfried output carries a 'warning' field for this; we surface
    it here so it is normalised into our warning schema regardless of engine.
    """
    warnings: list[IdentificationWarning] = []

    for result in tool_results:
        raw = result.raw_output or {}
        files = raw.get("files", [])
        for f in files:
            for match in f.get("matches", []):
                w = match.get("warning", "")
                if w and "extension" in w.lower():
                    warnings.append(
                        IdentificationWarning(
                            code="EXTENSION_MISMATCH",
                            message=w,
                        )
                    )

    return warnings


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class Orchestrator:
    def __init__(self, engines: list[BaseEngine]) -> None:
        self._engines = engines
        self._hierarchy = settings.registry_hierarchy

    async def identify_bytes(
        self,
        content: bytes,
        filename: Optional[str] = None,
        claimed_mimetype: Optional[str] = None,
        claimed_puid: Optional[str] = None,
    ) -> IdentificationResult:
        checksum = _sha256(content)
        tool_results = await self._run_all_bytes(content, filename)
        return self._build_result(
            tool_results,
            filename=filename,
            filesize=len(content),
            checksum=checksum,
            claimed_mimetype=claimed_mimetype,
            claimed_puid=claimed_puid,
        )

    async def identify_path(
        self,
        path: str,
        claimed_mimetype: Optional[str] = None,
        claimed_puid: Optional[str] = None,
    ) -> IdentificationResult:
        filename = Path(path).name
        try:
            with open(path, "rb") as fh:
                content = fh.read()
            filesize = len(content)
            checksum = _sha256(content)
        except OSError:
            filesize = None
            checksum = None

        tool_results = await self._run_all_path(path)
        return self._build_result(
            tool_results,
            filename=filename,
            filesize=filesize,
            checksum=checksum,
            claimed_mimetype=claimed_mimetype,
            claimed_puid=claimed_puid,
        )

    # ------------------------------------------------------------------

    async def _run_all_bytes(self, content: bytes, filename: Optional[str]) -> list[ToolResult]:
        tasks = [engine.identify_bytes(content, filename) for engine in self._engines]
        return list(await asyncio.gather(*tasks))

    async def _run_all_path(self, path: str) -> list[ToolResult]:
        tasks = [engine.identify_path(path) for engine in self._engines]
        return list(await asyncio.gather(*tasks))

    def _build_result(
        self,
        tool_results: list[ToolResult],
        filename: Optional[str],
        filesize: Optional[int],
        checksum: Optional[str],
        claimed_mimetype: Optional[str],
        claimed_puid: Optional[str],
    ) -> IdentificationResult:
        # Magika is fallback only: suppress its results if any other engine
        # produced a non-generic PRONOM identifier.
        primary_results = [r for r in tool_results if r.name != "magika"]
        primary_ids = _collect_all_identifiers(primary_results)
        has_pronom = any(i.scheme == "PRONOM" and not _is_generic(i) for i in primary_ids)

        effective_results = primary_results if has_pronom else tool_results

        all_identifiers = _collect_all_identifiers(effective_results)
        primary_identifier, basis = _select_primary(effective_results, self._hierarchy)

        warnings: list[IdentificationWarning] = []
        warnings.extend(_check_extension_mismatch(filename, primary_identifier, tool_results))

        # Multiple PRONOM matches → warning
        pronom_ids = [i for i in all_identifiers if i.scheme == "PRONOM" and not _is_generic(i)]
        if len(pronom_ids) > 1:
            warnings.append(
                IdentificationWarning(
                    code="MULTIPLE_MATCHES",
                    message=f"Multiple PRONOM identifiers found: {[i.value for i in pronom_ids]}",
                )
            )

        # Claimed MIME mismatch
        if claimed_mimetype and primary_identifier:
            mime_ids = [i for i in all_identifiers if i.scheme == "MIME"]
            if mime_ids and not any(i.value == claimed_mimetype for i in mime_ids):
                warnings.append(
                    IdentificationWarning(
                        code="CLAIMED_MIME_MISMATCH",
                        message=(
                            f"Claimed MIME type '{claimed_mimetype}' does not match "
                            f"identified type(s): {[i.value for i in mime_ids]}"
                        ),
                    )
                )

        # Claimed PUID mismatch
        if claimed_puid and primary_identifier:
            if not any(i.scheme == "PRONOM" and i.value == claimed_puid for i in all_identifiers):
                warnings.append(
                    IdentificationWarning(
                        code="CLAIMED_PUID_MISMATCH",
                        message=(
                            f"Claimed PUID '{claimed_puid}' does not match "
                            f"identified PRONOM identifier(s): {[i.value for i in pronom_ids]}"
                        ),
                    )
                )

        # Determine outcome
        if primary_identifier and not _is_generic(primary_identifier):
            outcome = IdentificationOutcome.WARNING if warnings else IdentificationOutcome.SUCCESS
        else:
            outcome = IdentificationOutcome.FAILURE
            warnings.append(
                IdentificationWarning(
                    code="NO_MATCH",
                    message="File could not be identified in any registry. Manual review advised.",
                )
            )

        provenance = ProvenanceMetadata(
            date=datetime.now(tz=timezone.utc),
            outcome=outcome,
            tools=tool_results,
        )

        return IdentificationResult(
            filename=filename,
            filesize=filesize,
            checksum_sha256=checksum,
            identifiers=all_identifiers,
            primary_identifier=primary_identifier,
            basis=basis,
            warnings=warnings,
            provenance=provenance,
        )
