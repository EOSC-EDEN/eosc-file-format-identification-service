"""
Pydantic models for FFIS identification results.

Output schema follows FFIS-REQ-2-03 and the CPP-008 output requirements:
  - identifiers with value, scheme, and optional URI
  - full provenance (tools used, raw outputs, date, outcome)
  - extension/MIME mismatch warnings (FFIS-REQ-3-04)
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class IdentificationOutcome(str, Enum):
    SUCCESS = "success"
    WARNING = "warning"   # identified with caveats (e.g. multiple matches, extension mismatch)
    FAILURE = "failure"   # no registry match found — flag for manual review


class IdentificationMethod(str, Enum):
    BYTE_SIGNATURE = "byte signature"
    CONTAINER_SIGNATURE = "container signature"
    XML_STRUCTURE = "xml structure"
    AI_PROBABILISTIC = "ai/probabilistic"
    MIME_MAGIC = "mime magic"
    EXTENSION = "extension"
    UNKNOWN = "unknown"


class Identifier(BaseModel):
    """A single format identifier from one registry (FFIS-REQ-2-01, FFIS-REQ-2-03)."""

    value: str                  # e.g. "fmt/412" or "application/pdf"
    scheme: str                 # e.g. "PRONOM", "MIME", "WIKIDATA", "LOC"
    uri: Optional[str] = None   # e.g. "https://www.nationalarchives.gov.uk/pronom/fmt/412"


class ToolResult(BaseModel):
    """Raw result from one identification engine (FFIS-REQ-3-02)."""

    name: str
    version: Optional[str] = None
    identifiers: list[Identifier] = []
    method: Optional[IdentificationMethod] = None
    format_name: Optional[str] = None      # human-readable format name from the tool
    format_version: Optional[str] = None   # e.g. "1.7"
    raw_output: Optional[dict] = None
    error: Optional[str] = None


class IdentificationWarning(BaseModel):
    """A non-fatal advisory attached to a result (FFIS-REQ-3-04)."""

    code: str       # e.g. "EXTENSION_MISMATCH", "MULTIPLE_MATCHES", "NO_MATCH"
    message: str


class ProvenanceMetadata(BaseModel):
    """Full provenance record required by CPP-008 output spec."""

    date: datetime
    outcome: IdentificationOutcome
    tools: list[ToolResult] = []


class IdentificationResult(BaseModel):
    """Complete identification result returned by the FFIS API."""

    filename: Optional[str] = None
    filesize: Optional[int] = None
    checksum_sha256: Optional[str] = None

    # All identifiers collected across all tools, deduplicated
    identifiers: list[Identifier] = []

    # Single winning identifier after conflict resolution (FFIS-REQ-3-03)
    primary_identifier: Optional[Identifier] = None

    # Method used by the winning engine
    basis: Optional[IdentificationMethod] = None

    warnings: list[IdentificationWarning] = []
    provenance: ProvenanceMetadata
    cached: bool = False


class IdentifyByPathRequest(BaseModel):
    """Request body for the by-reference input mode (FFIS-REQ-4-01)."""

    path: str
    claimed_mimetype: Optional[str] = None
    claimed_puid: Optional[str] = None
