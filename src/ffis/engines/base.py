"""Abstract base class for identification engines."""

from abc import ABC, abstractmethod
from typing import Optional

from ..models.identification import ToolResult


class BaseEngine(ABC):
    name: str

    @abstractmethod
    async def identify_bytes(self, content: bytes, filename: Optional[str] = None) -> ToolResult:
        """Identify a file supplied as raw bytes (by-value input mode)."""

    @abstractmethod
    async def identify_path(self, path: str) -> ToolResult:
        """Identify a file by filesystem path (by-reference input mode)."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if this engine is reachable and usable."""

    @abstractmethod
    async def get_version(self) -> Optional[str]:
        """Return the engine version string, or None if unavailable."""
