# RunPod Custom Image (Symmetric Port) Setup

This guide shows how to build and use a custom container image that boots with
everything pre-configured for the Texas steering pilot and batch pipelines. The
container handles SSH, virtualenv creation, dependency installation (`sae-lens`,
`nnterp`), and `env.sh` generation automatically using the persistent volume
mounted at `/workspace/graphs/giuseppe`.

## Directory layout

The repository now contains:

```
docker/runpod/Dockerfile      # Custom image definition
docker/runpod/entrypoint.sh   # Boot script (executed every time the pod starts)
docker/runpod/runpod_docker.md# This guide
```

The entrypoint expects a persistent network volume mounted at
`/workspace/graphs/giuseppe` with the following contents (created automatically
on first boot):

```
/workspace/graphs/giuseppe/
├── attribution-graph-probing/      # repo checkout (cloned if missing)
├── attribution-graph-probing/.venv # virtualenv with requirements + sae-lens + nnterp
├── env.sh                          # activation script (source this on the pod)
├── hf_cache/                       # HuggingFace cache
└── logs/                           # remote logs
```

## Build & publish the image

1. Clone/pull the repo locally.
2. Build the image (adjust tag/registry as desired):

   ```bash
   docker build \
     -f docker/runpod/Dockerfile \
     -t ghcr.io/<your-org>/attribution-graph-probing-runpod:latest \
     .
   ```

3. Push it to the registry RunPod can access:

   ```bash
   docker push ghcr.io/<your-org>/attribution-graph-probing-runpod:latest
   ```

## Configure the RunPod template

When creating the pod template:

1. **Image**: use the tag you pushed (e.g.
   `ghcr.io/<your-org>/attribution-graph-probing-runpod:latest`).
2. **Expose TCP Ports**: add `70022`. RunPod will set
   `RUNPOD_TCP_PORT_70022` at runtime, and the entrypoint configures sshd to
   listen on that port so external/internal numbers match.
3. **Volumes**:
   - Attach a network volume (same region as the pod).
   - Mount it at `/workspace/graphs/giuseppe`.
4. **Environment variables**:
   - `PUBLIC_KEY=ssh-ed25519 AAAA...` (your Windows public key), or use
     `SSH_PUBLIC_KEY`.
   - Optional `GITHUB_TOKEN=ghp_...` if `nnterp` is private. The entrypoint runs
     `pip install git+https://${GITHUB_TOKEN}@github.com/Oldunein/nnterp.git`
     when this variable is set.
5. **Command**: leave empty; the Dockerfile already sets `CMD` to the entrypoint.

Once the pod starts, the entrypoint:

1. Configures sshd with the symmetric port (read from
   `RUNPOD_TCP_PORT_70022`, fallback 22).
2. Writes `/root/.ssh/authorized_keys` from `PUBLIC_KEY` / `SSH_PUBLIC_KEY`.
3. Clones the repo into the volume (if missing).
4. Creates/updates the virtualenv, installs `requirements.txt`, `sae-lens`,
   and `nnterp`.
5. Writes `/workspace/graphs/giuseppe/env.sh`.
6. Keeps the container alive via `tail -f /dev/null` for SSH access.

## Laptop SSH configuration (static)

Because the pod listens on the symmetric port, the local ssh config can stay
unchanged:

```
Host runpod-gpu
    HostName <RunPod public IP>
    Port 70022
    User root
    IdentityFile C:/Users/OrmaLabUser/.ssh/id_ed25519
```

No more port updates after restarts.

## Daily workflow

1. Start the RunPod pod with this template.
2. SSH from Windows:

   ```powershell
   ssh runpod-gpu
   ```

3. (Optional) verify the environment on the pod:

   ```bash
   source /workspace/graphs/giuseppe/env.sh
   python -c "import sae_lens, nnterp; print('remote env ok')"
   ```

4. Run pilots or batches from your laptop using
   `scripts/experiments/batch/configs/usa_states_full_runpod.yml`.

## GitHub Actions automation

The repository includes `.github/workflows/runpod-image.yml`, which keeps the
image up to date automatically:

- pushes to `main` build and publish `ghcr.io/peppinob-ol/attribution-graph-probing-runpod:latest`
  (edit `env.IMAGE_NAME` if you fork or use a different registry),
- tags matching `v*` publish both `:latest` and the specific `:vX.Y.Z` tag.

Because the workflow upgrades the image on every commit/tag, your RunPod
template can stay pointed at `:latest` (or a pinned release tag) without any
manual `docker build/push` steps.

