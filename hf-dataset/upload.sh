#!/usr/bin/env bash
# Upload the benchmark CSV + this card as a public Hugging Face dataset.
# Needs: `pip install huggingface_hub` and a write token (`huggingface-cli login`, or HF_TOKEN in the env).
# Neither was present on hpbuntu on 2026-10-08, so this is staged for whoever holds the account.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${1:-petronellatech/gb10-cluster-bandwidth}"
command -v huggingface-cli >/dev/null || { echo "huggingface-cli not installed (pip install huggingface_hub)"; exit 2; }
huggingface-cli repo create "$REPO" --type dataset --exist-ok
huggingface-cli upload "$REPO" "$HERE/../data/gb10-cluster-bandwidth-2026.csv" gb10-cluster-bandwidth-2026.csv --repo-type dataset
huggingface-cli upload "$REPO" "$HERE/README.md" README.md --repo-type dataset
echo "https://huggingface.co/datasets/$REPO"
