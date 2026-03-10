#!/usr/bin/env bash
# Export SPECIFICATION.md to DOCX for Google Docs import.
#
# Usage:
#   ./export-spec.sh                    # outputs SPECIFICATION.docx
#   ./export-spec.sh my-output.docx     # custom output filename
#
# Requires pandoc (https://pandoc.org/installing.html).
# If pandoc is not installed locally, falls back to Docker.

set -euo pipefail

INPUT="SPECIFICATION.md"
OUTPUT="${1:-SPECIFICATION.docx}"

if [ ! -f "$INPUT" ]; then
  echo "Error: $INPUT not found. Run from the repository root." >&2
  exit 1
fi

convert_with_pandoc() {
  pandoc "$INPUT" \
    --from=gfm \
    --to=docx \
    --standalone \
    --toc \
    --metadata title="FFIS Specification" \
    -o "$OUTPUT"
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
    "$INPUT" \
      --from=gfm \
      --to=docx \
      --standalone \
      --toc \
      --metadata title="FFIS Specification" \
      -o "$OUTPUT"
}

if command -v pandoc &>/dev/null; then
  convert_with_pandoc
else
  convert_with_docker
fi

echo "Exported: $OUTPUT"
echo "Upload to Google Docs: https://docs.google.com → File → Open → Upload"
