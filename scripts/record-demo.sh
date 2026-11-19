#!/usr/bin/env bash
# Start the demo on loopback with a fresh database for each recording.
set -euo pipefail
cd -- "$(dirname -- "$0")/.."

python_bin="${WORKBENCH_PYTHON:-python3.11}"
api_port="${WORKBENCH_API_PORT:-8000}"
ui_port="${WORKBENCH_UI_PORT:-8501}"
export PYTHONPATH=src
export MODEL_DIR="${MODEL_DIR:-artifacts/models}"

if ! "$python_bin" -c 'import uvicorn, streamlit, sklearn' >/dev/null 2>&1; then
    printf '%s\n' 'Activate the Python 3.11 environment with requirements-dev.txt installed, or set WORKBENCH_PYTHON.' >&2
    exit 1
fi

if [[ ! -d "$MODEL_DIR" ]]; then
    "$python_bin" -m lab_workbench.train --output "$MODEL_DIR"
fi

recording_dir="$(mktemp -d "${TMPDIR:-/tmp}/lab-workbench-take.XXXXXXXX")"
export WORKBENCH_DB="$recording_dir/workbench.sqlite3"
export WORKBENCH_API="http://127.0.0.1:$api_port"

"$python_bin" -m uvicorn lab_workbench.api:app --host 127.0.0.1 --port "$api_port" &
api_pid=$!
cleanup() {
    kill "$api_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT TERM

printf 'Recording database: %s\nStreamlit: http://127.0.0.1:%s\n' "$WORKBENCH_DB" "$ui_port"
"$python_bin" -m streamlit run src/lab_workbench/ui.py \
    --server.address=127.0.0.1 --server.port="$ui_port" --server.headless=true
