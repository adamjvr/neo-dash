#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    :
elif REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)"; then
    :
else
    printf 'error: run this patch from inside the NeoDash Git repository\n' >&2
    exit 1
fi

cd "$REPO_ROOT"
python3 "$SCRIPT_DIR/apply_runtime_event_stream.py" "$REPO_ROOT"

printf '\nValidation gate:\n'
printf '  cargo fmt --all\n'
printf '  ./scripts/check_runtime_stream.sh\n'
printf '  cargo run -p neodash-daemon -- --widget examples/widgets/date.toml --frames 3\n'
