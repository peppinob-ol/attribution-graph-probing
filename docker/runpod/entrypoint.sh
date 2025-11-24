#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="/workspace/graphs/giuseppe"
REPO_DIR="${APP_ROOT}/attribution-graph-probing"
VENV_DIR="${REPO_DIR}/.venv"
ENV_FILE="${APP_ROOT}/env.sh"
LOG_PREFIX="[RUNPOD]"

echo "$LOG_PREFIX Using APP_ROOT=$APP_ROOT"
mkdir -p "${APP_ROOT}/logs" "${APP_ROOT}/hf_cache"

# Expected symmetric port passed from RunPod via RUNPOD_TCP_PORT_55222.
SSH_PORT="${RUNPOD_TCP_PORT_55222:-55222}"
echo "$LOG_PREFIX Configuring sshd on port ${SSH_PORT}"

cat >/etc/ssh/sshd_config <<EOF
Port ${SSH_PORT}
Protocol 2
HostKey /etc/ssh/ssh_host_ed25519_key
PermitRootLogin prohibit-password
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
ChallengeResponseAuthentication no
Subsystem sftp /usr/lib/openssh/sftp-server
EOF

if [ ! -f /etc/ssh/ssh_host_ed25519_key ]; then
  echo "$LOG_PREFIX Generating host key"
  ssh-keygen -t ed25519 -N "" -f /etc/ssh/ssh_host_ed25519_key
fi

mkdir -p /root/.ssh
chmod 700 /root/.ssh
if [ -n "${PUBLIC_KEY:-}" ]; then
  printf "%s\n" "$PUBLIC_KEY" > /root/.ssh/authorized_keys
elif [ -n "${SSH_PUBLIC_KEY:-}" ]; then
  printf "%s\n" "$SSH_PUBLIC_KEY" > /root/.ssh/authorized_keys
else
  echo "$LOG_PREFIX WARNING: no PUBLIC_KEY/SSH_PUBLIC_KEY supplied; SSH login will fail."
fi
chmod 600 /root/.ssh/authorized_keys

service ssh restart

###############################################################################
# Repo + virtualenv on the persistent volume
###############################################################################

if [ ! -d "$REPO_DIR/.git" ]; then
  echo "$LOG_PREFIX Cloning repository into volume"
  rm -rf "$REPO_DIR"
  git clone --depth 1 https://github.com/peppinob-ol/attribution-graph-probing.git "$REPO_DIR"
else
  echo "$LOG_PREFIX Repository already present; skipping clone"
fi

if [ ! -d "$VENV_DIR" ]; then
  echo "$LOG_PREFIX Creating virtualenv at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

echo "$LOG_PREFIX Activating virtualenv"
# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip setuptools wheel

REQ_FILE="${REPO_DIR}/requirements.txt"
if [ -f "$REQ_FILE" ]; then
  echo "$LOG_PREFIX Installing repo requirements"
  pip install -r "$REQ_FILE"
else
  echo "$LOG_PREFIX WARNING: $REQ_FILE missing; skipping requirements install"
fi

echo "$LOG_PREFIX Installing sae-lens"
pip install --upgrade sae-lens

if [ -n "${GITHUB_TOKEN:-}" ]; then
  echo "$LOG_PREFIX Installing nnterp with provided GITHUB_TOKEN"
  pip install --upgrade "git+https://${GITHUB_TOKEN}@github.com/Oldunein/nnterp.git"
else
  echo "$LOG_PREFIX NOTE: GITHUB_TOKEN not set; nnterp not installed"
fi

echo "$LOG_PREFIX Writing env activator to $ENV_FILE"
cat >"$ENV_FILE" <<'EOF'
source /workspace/graphs/giuseppe/attribution-graph-probing/.venv/bin/activate
export HF_HOME=/workspace/graphs/giuseppe/hf_cache
export NP_WORKDIR=/workspace/graphs/giuseppe
EOF
chmod +x "$ENV_FILE"

echo "$LOG_PREFIX Bootstrap complete. Container will now idle for SSH access."
tail -f /dev/null

