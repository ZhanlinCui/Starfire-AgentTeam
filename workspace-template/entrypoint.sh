#!/bin/bash
set -e

# Ensure user-installed packages are in PATH
export PATH="$HOME/.local/bin:$PATH"

# Determine runtime from config.yaml
RUNTIME=$(python3 -c "
import yaml
from pathlib import Path
cfg_path = Path('/configs/config.yaml')
if cfg_path.exists():
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    print(cfg.get('runtime', 'langgraph'))
else:
    print('langgraph')
" 2>/dev/null || echo "langgraph")

# Normalize runtime name for directory lookup (claude-code -> claude_code)
ADAPTER_DIR=$(echo "$RUNTIME" | tr '-' '_')

echo "=== Agent Molecule Workspace ==="
echo "Runtime: $RUNTIME"

# Install adapter-specific Python requirements (skip if already pre-installed in image)
REQ_FILE="/app/adapters/${ADAPTER_DIR}/requirements.txt"
if [ -f "$REQ_FILE" ]; then
    if grep -q '^[^#]' "$REQ_FILE" 2>/dev/null; then
        # Check if first package is already installed
        FIRST_PKG=$(grep '^[^#]' "$REQ_FILE" | head -1 | sed 's/[>=<].*//')
        if python3 -c "import importlib; importlib.import_module('${FIRST_PKG//-/_}')" 2>/dev/null; then
            echo "Adapter deps already installed (${FIRST_PKG})"
        else
            echo "Installing Python adapter dependencies..."
            pip install --no-cache-dir --user -q -r "$REQ_FILE" 2>&1 | tail -3
        fi
    fi
fi

# Install adapter-specific npm packages (for Node.js-based runtimes like OpenClaw)
NPM_FILE="/app/adapters/${ADAPTER_DIR}/package.json"
if [ -f "$NPM_FILE" ]; then
    echo "Installing npm adapter dependencies..."
    cd "/app/adapters/${ADAPTER_DIR}" && npm install --production 2>&1 | tail -3
    cd /app
fi

exec python3 main.py
