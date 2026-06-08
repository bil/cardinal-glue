#!/bin/bash
set -e

if [ "$#" -eq 0 ]; then
    echo "Usage: bash wg_tool.sh <command> [args]"
    exit 1
fi

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$HOME/.gemini/venvs/stanford-workgroup"

# Create venv and install cardinal-glue if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Initializing dedicated virtual environment at $VENV_DIR..." >&2
    mkdir -p "$(dirname "$VENV_DIR")"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet git+https://github.com/bil/cardinal-glue.git
fi

# Run the python script using the venv's python
"$VENV_DIR/bin/python" "$SCRIPT_DIR/wg_tool.py" "$@"