#!/usr/bin/env bash
# Download only the Sky130 device models this project uses.
# The repository is cloned without file contents (blob:none), then just the
# needed folders are checked out, pinned to one commit so results are repeatable.
set -euo pipefail

ROOT="${SKY130_PDK_ROOT:-$HOME/.cache/sky130-analog-blocks/pdk-src}"
COMMIT="f62031a1be9aefe902d6d54cddd6f59b57627436"
REPO="https://github.com/google/skywater-pdk-libs-sky130_fd_pr.git"

if [ ! -d "$ROOT/.git" ]; then
  mkdir -p "$(dirname "$ROOT")"
  git clone --filter=blob:none --no-checkout --sparse "$REPO" "$ROOT"
fi
cd "$ROOT"
git sparse-checkout set --no-cone \
  "/models/" "/cells/nfet_01v8/" "/cells/pfet_01v8/" "/cells/pnp_05v5/"
git fetch --filter=blob:none origin "$COMMIT"
git checkout -q "$COMMIT"
echo "Sky130 device models ready at $ROOT (commit ${COMMIT:0:12})"
