#!/usr/bin/env bash
#
# Template bootstrap script for RunPod pods.
# Copy this file to /workspace/graphs/giuseppe/runpod_bootstrap.sh on the pod,
# adjust TOKEN or paths if needed, and run it after each pod restart.
#
# It is intentionally standalone so that you can paste/run it via Web Terminal.

set -euo pipefail

VOLUME_ROOT="/workspace/graphs/giuseppe"
REPO_DIR="$VOLUME_ROOT/attribution-graph-probing"
VENV_DIR="$REPO_DIR/.venv"
ENV_FILE="$VOLUME_ROOT/env.sh"
LOG_PREFIX="[BOOTSTRAP]"

echo "$LOG_PREFIX Ensuring openssh-server is installed..."
if ! command -v sshd >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y openssh-server
fi
sudo service ssh restart

echo "$LOG_PREFIX Using volume root: $VOLUME_ROOT"
mkdir -p "$VOLUME_ROOT"

if [ ! -d "$REPO_DIR" ]; then
    echo "$LOG_PREFIX ERROR: $REPO_DIR not found. Clone the repo onto the volume first."
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    echo "$LOG_PREFIX Creating virtualenv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
fi

echo "$LOG_PREFIX Activating virtualenv"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel

REQ_FILE="$REPO_DIR/requirements.txt"
if [ -f "$REQ_FILE" ]; then
    echo "$LOG_PREFIX Installing requirements..."
    pip install -r "$REQ_FILE"
else
    echo "$LOG_PREFIX WARNING: $REQ_FILE missing; skipping base requirements."
fi

echo "$LOG_PREFIX Installing sae-lens..."
pip install --upgrade sae-lens

echo "$LOG_PREFIX Writing $ENV_FILE"
cat > "$ENV_FILE" <<'EOF'
source /workspace/graphs/giuseppe/attribution-graph-probing/.venv/bin/activate
export HF_HOME=/workspace/graphs/giuseppe/hf_cache
export NP_WORKDIR=/workspace/graphs/giuseppe
EOF
chmod +x "$ENV_FILE"

echo "$LOG_PREFIX Bootstrap complete. You can now SSH from Windows and run the pilots."

