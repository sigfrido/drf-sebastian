#!/usr/bin/env bash
# Regenerate the API reference at docs/api/ from the sebastian source docstrings.
# Requires the dev extra: pip install -e ".[dev]"
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf docs/api
PYTHONPATH=src:testproject DJANGO_SETTINGS_MODULE=settings \
    python -m pdoc sebastian -o docs/api --docformat restructuredtext

echo "Generated docs/api/index.html"
