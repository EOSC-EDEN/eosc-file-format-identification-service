# eosc-ffis

EOSC EDEN File Format Identification Service

A multi-engine file format identification service implementing the [EOSC EDEN FFIS specification](https://github.com/EOSC-EDEN/wp1-cpp-descriptions/blob/main/CPP-008/EOSC-EDEN_CPP-008_File_Format_Identification.pdf).

Orchestrates [Siegfried](https://www.itforarchivists.com/siegfried), [Google Magika](https://github.com/google/magika), and optionally [Apache Tika](https://tika.apache.org/) to produce registry-mapped format identifiers with full provenance — ready for use in OAIS-compliant preservation workflows.

---

## Why this exists

Digital archives cannot reliably migrate, render, or emulate files without knowing their format. File extensions and user-supplied MIME types are unreliable. This service performs identification against binary signatures and maps results to standardised registries (PRONOM, MIME, Wikidata), providing the prerequisite input for preservation planning, format migration, and ingest verification.

---

## Features

- Multi-engine orchestration — Siegfried (primary), Magika (AI fallback), Tika (optional)
- Deterministic conflict resolution — registry hierarchy (PRONOM > LOC > Wikidata > MIME) and method priority (byte signature > container > AI)
- Two input modes — upload by value or identify by filesystem path (zero-copy for containerised deployments)
- Full provenance — every result records which tools ran, their raw outputs, and the outcome
- Extension/MIME mismatch warnings — flags discrepancies between claimed and identified format
- SQLite result cache — keyed by SHA-256 checksum; avoids re-processing identical files
- PRONOM URI links — every PRONOM identifier includes a resolvable URI to the registry record
- OpenAPI docs — auto-generated at `/docs`

---

## Quick start

### Docker (recommended)

```bash
docker compose up --build
```

The API is available at `http://localhost:8000`.
Interactive docs at `http://localhost:8000/docs`.

### Local (development)

Requires Python 3.11+ and the `sf` binary on `$PATH`.

```bash
# Install Siegfried (https://www.itforarchivists.com/siegfried)
# Linux example:
curl -fsSL https://github.com/richardlehane/siegfried/releases/download/v1.11.1/siegfried_1.11.1_linux64.tar.gz \
  | tar -xzf - -C /usr/local/bin sf
sf -update

# Install the service
pip install -e ".[dev]"

# Run
ffis
# or
uvicorn ffis.main:app --reload
```

---

## API

### `POST /identify` — identify by value (file upload)

Upload a file directly. The filename and any claimed MIME type are used only for mismatch verification, never for identification.

```bash
curl -X POST http://localhost:8000/identify \
  -F "file=@/path/to/document.pdf" \
  -F "claimed_mimetype=application/pdf"
```

### `POST /identify/path` — identify by reference (filesystem path)

Pass a path to a file accessible to the service container. No data is transferred over the network — the service reads from a shared volume.

```bash
curl -X POST http://localhost:8000/identify/path \
  -H "Content-Type: application/json" \
  -d '{"path": "/mnt/tda-storage/objects/document.pdf"}'
```

### `GET /health`

Liveness check.

### `GET /tools`

Lists configured engines, their availability, and version strings.

---

## Example response

```json
{
  "filename": "document.pdf",
  "filesize": 84231,
  "checksum_sha256": "a3f2...",
  "identifiers": [
    {
      "value": "fmt/412",
      "scheme": "PRONOM",
      "uri": "https://www.nationalarchives.gov.uk/pronom/fmt/412"
    },
    {
      "value": "application/pdf",
      "scheme": "MIME",
      "uri": null
    }
  ],
  "primary_identifier": {
    "value": "fmt/412",
    "scheme": "PRONOM",
    "uri": "https://www.nationalarchives.gov.uk/pronom/fmt/412"
  },
  "basis": "byte signature",
  "warnings": [],
  "provenance": {
    "date": "2026-02-20T10:00:00Z",
    "outcome": "success",
    "tools": [
      {
        "name": "siegfried",
        "version": "1.11.1",
        "identifiers": [...],
        "method": "byte signature",
        "format_name": "Acrobat PDF 1.3 - Portable Document Format",
        "format_version": "1.3",
        "raw_output": {...}
      }
    ]
  },
  "cached": false
}
```

Outcome values:

| Value     | Meaning                                                                           |
| --------- | --------------------------------------------------------------------------------- |
| `success` | Format identified with no caveats                                                 |
| `warning` | Identified but with advisories (e.g. extension mismatch, multiple PRONOM matches) |
| `failure` | Could not be identified — manual review advised                                   |

---

## Configuration

All settings are environment variables prefixed `FFIS_`. Copy `.env.example` to `.env` to customise.

| Variable                    | Default                    | Description                |
| --------------------------- | -------------------------- | -------------------------- |
| `FFIS_SIEGFRIED_BINARY`     | `sf`                       | Path to Siegfried binary   |
| `FFIS_SIEGFRIED_SERVER_URL` | _(unset)_                  | Siegfried REST sidecar URL |
| `FFIS_MAGIKA_ENABLED`       | `true`                     | Enable Magika AI fallback  |
| `FFIS_TIKA_ENABLED`         | `false`                    | Enable Apache Tika engine  |
| `FFIS_TIKA_SERVER_URL`      | _(unset)_                  | Tika REST server URL       |
| `FFIS_CACHE_ENABLED`        | `true`                     | Enable SQLite result cache |
| `FFIS_CACHE_DB_PATH`        | `/tmp/ffis_cache.db`       | Cache database path        |
| `FFIS_REGISTRY_HIERARCHY`   | `PRONOM,LOC,WIKIDATA,MIME` | Conflict resolution order  |
| `FFIS_API_PORT`             | `8000`                     | HTTP port                  |

---

## Deployment patterns

### Standalone container (small TDA)

Use `docker compose up`. Siegfried runs inside the image; results are cached in a named volume.

### Shared-volume / zero-copy (large TDA)

Mount your storage into the container and use `POST /identify/path`. Multiple preservation service containers (virus scanner, fixity checker, metadata extractor) can share the same read-only volume and chain their analysis without data duplication, as recommended by the FFIS specification.

```yaml
volumes:
  - /mnt/tda-storage:/mnt/tda-storage:ro
```

### Tika sidecar (scientific data)

Uncomment the `tika` service block in `docker-compose.yml` and set `FFIS_TIKA_ENABLED=true` and `FFIS_TIKA_SERVER_URL=http://tika:9998`.

---

## Running tests

```bash
pip install -e ".[dev]"
pytest
```

---

## Specification conformance

| Requirement                                      | Status                           |
| ------------------------------------------------ | -------------------------------- |
| FFIS-REQ-1-01 Binary signature identification    | Siegfried                        |
| FFIS-REQ-1-02 No extension-only identification   | Enforced                         |
| FFIS-REQ-1-03 Version/profile granularity        | Siegfried                        |
| FFIS-REQ-1-04 Multiple engine integration        | Siegfried + Magika + Tika        |
| FFIS-REQ-2-01 Registry identifier mapping        | PRONOM + MIME + Wikidata         |
| FFIS-REQ-2-02 MIME type reporting                | All results                      |
| FFIS-REQ-2-03 Machine-actionable JSON output     | FastAPI/JSON                     |
| FFIS-REQ-3-01 Basis of identification reported   | `basis` field                    |
| FFIS-REQ-3-02 Full provenance (all tool outputs) | `provenance.tools`               |
| FFIS-REQ-3-03 Deterministic conflict resolution  | Registry + method hierarchy      |
| FFIS-REQ-3-04 Extension mismatch warnings        | `warnings` array                 |
| FFIS-REQ-4-01 By-value and by-reference input    | `/identify` and `/identify/path` |

---

## References

- [EOSC EDEN FFIS Specification](https://github.com/EOSC-EDEN/wp1-cpp-descriptions)
- [CPP-008 File Format Identification](https://github.com/EOSC-EDEN/wp1-cpp-descriptions/blob/main/CPP-008/)
- [PRONOM Technical Registry](https://www.nationalarchives.gov.uk/PRONOM/)
- [Siegfried](https://www.itforarchivists.com/siegfried)
- [Google Magika](https://github.com/google/magika)
- [ISO 14721:2012 OAIS Reference Model](https://www.iso.org/standard/57284.html)
- [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119)
