#!/usr/bin/env bash
# Export SPECIFICATION.md to DOCX for Google Docs import.
#
# Usage:
#   ./export-spec.sh                                          # outputs "File Format Identification Service.docx"
#   ./export-spec.sh "my-output.docx"                         # custom output filename
#
# Requires pandoc (https://pandoc.org/installing.html).
# If pandoc is not installed locally, falls back to Docker/Podman.
#
# Fonts: body text = Cambria, headings = Calibri (via reference.docx)

set -euo pipefail

INPUT="docs/specification.md"
OUTPUT="${1:-File Format Identification Service.docx}"
REFERENCE="reference.docx"
TMPINPUT=".export-spec-tmp.md"

if [ ! -f "$INPUT" ]; then
  echo "Error: $INPUT not found. Run from the repository root." >&2
  exit 1
fi

if [ ! -f "$REFERENCE" ]; then
  echo "Error: $REFERENCE not found. Run from the repository root." >&2
  exit 1
fi

# Prepend a read-only notice for the exported .docx
trap 'rm -f "$TMPINPUT"' EXIT
cat > "$TMPINPUT" << 'NOTICE'
> **NOTE: This document has been exported from GitHub and is read-only.**
> As per agreement with EOSC EDEN WP3, for user acceptance testing, this specification has moved to GitHub.
> The source of truth is now:
> https://github.com/EOSC-EDEN/eosc-file-format-identification-tool/blob/main/docs/specification.md
> To comment or suggest changes, please open an issue or pull request.
> A `.docx` export can be generated locally by running `./export-spec.sh` from the repository root.

---

NOTICE
cat "$INPUT" >> "$TMPINPUT"

PANDOC_ARGS=(
  "$TMPINPUT"
  --from=gfm
  --to=docx
  --standalone
  --toc
  --reference-doc="$REFERENCE"
  --metadata title="File Format Identification Service"
  -o "$OUTPUT"
)

convert_with_pandoc() {
  pandoc "${PANDOC_ARGS[@]}"
}

convert_with_docker() {
  local container_engine
  if command -v docker &>/dev/null; then
    container_engine=docker
  elif command -v podman &>/dev/null; then
    container_engine=podman
  else
    echo "Error: Neither pandoc, docker, nor podman found." >&2
    echo "Install pandoc: https://pandoc.org/installing.html" >&2
    exit 1
  fi

  echo "pandoc not found locally, using $container_engine..."
  local userns_flag=""
  if [ "$container_engine" = "podman" ]; then
    userns_flag="--userns=keep-id"
  fi

  "$container_engine" run --rm \
    $userns_flag \
    -v "$(pwd):/data:Z" \
    -w /data \
    docker.io/pandoc/core \
    "${PANDOC_ARGS[@]}"
}

if command -v pandoc &>/dev/null; then
  convert_with_pandoc
else
  convert_with_docker
fi

echo "Exported: $OUTPUT"
echo "Upload to Google Docs: https://docs.google.com → File → Open → Upload"
