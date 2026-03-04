"""
EOSC EDEN File Format Identification Service — application entry point.

Bootstraps engines, orchestrator, and cache, then starts the FastAPI server.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.routes import router
from .cache import IdentificationCache
from .config import settings
from .engines.base import BaseEngine
from .engines.magika import MagikaEngine
from .engines.siegfried import SiegfriedEngine
from .engines.tika import TikaEngine
from .orchestrator import Orchestrator


def _build_engines() -> list[BaseEngine]:
    engines: list[BaseEngine] = []

    # Siegfried — always primary
    engines.append(
        SiegfriedEngine(
            binary=settings.siegfried_binary,
            server_url=settings.siegfried_server_url,
        )
    )

    # Magika — AI fallback, optional
    if settings.magika_enabled:
        engines.append(MagikaEngine())

    # Apache Tika — optional, scientific/rich-media coverage
    if settings.tika_enabled:
        engines.append(TikaEngine(server_url=settings.tika_server_url))

    return engines


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    engines = _build_engines()
    app.state.engines = engines
    app.state.orchestrator = Orchestrator(engines)
    app.state.settings = settings

    if settings.cache_enabled:
        cache = IdentificationCache(settings.cache_db_path)
        await cache.setup()
        app.state.cache = cache
    else:
        app.state.cache = None

    yield


app = FastAPI(
    title="EOSC EDEN File Format Identification Service",
    description=(
        "Multi-engine file format identification service implementing the EOSC EDEN FFIS "
        "specification. Orchestrates Siegfried, Magika, and Apache Tika to produce "
        "registry-mapped identifiers (PRONOM, MIME, Wikidata) with full provenance."
    ),
    version=__version__,
    lifespan=lifespan,
    contact={
        "name": "EOSC EDEN",
        "url": "https://github.com/EOSC-EDEN",
    },
    license_info={
        "name": "Apache 2.0",
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, tags=["Identification"])

_static = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_static, html=True), name="static")


def cli() -> None:
    import uvicorn
    uvicorn.run(
        "ffis.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    cli()
