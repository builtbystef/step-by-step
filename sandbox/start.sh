#!/usr/bin/env bash
# Starts the step-by-step agent sandbox. THIS SCRIPT RUNS ON THE HOST.
# A sandboxed agent can edit this file, and the edits run on your host the
# next time that you start it. Review `git diff -- sandbox/` before each
# start.
#
# The security flags (--cap-drop, --security-opt, the mount list) are the
# sandbox boundary. Do not weaken them. The resource limits below them only
# protect the host. Edit those freely.
#
# --network=host is deliberate: the infrastructure stack runs on the host
# under Docker, and the sandbox reaches Postgres, Redis and Garage on
# localhost through the URLs in .env. It grants no filesystem access and no
# container control — the network was never the boundary here.
#
# The --dns lines are not a preference: the host resolves through the
# systemd-resolved stub at 127.0.0.53, which a rootless container cannot
# reach, so names have to resolve upstream. Point them at your own resolver
# if you would rather not use these.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"
NAME="sandbox-step-by-step"

tty_flags="-i"
[ -t 0 ] && tty_flags="-it"

exec podman run \
  --rm $tty_flags \
  --name "$NAME" \
  --cap-drop=all \
  --security-opt=no-new-privileges \
  --userns=keep-id:uid=1000,gid=1000 \
  --network=host \
  --dns 1.1.1.1 \
  --dns 8.8.8.8 \
  --pids-limit=2048 \
  --memory=8g \
  --cpus=6 \
  --volume "$REPO:/workspace" \
  --volume "$NAME-home:/home/agent" \
  --env "GIT_AUTHOR_NAME=$(git config user.name)" \
  --env "GIT_AUTHOR_EMAIL=$(git config user.email)" \
  --env "GIT_COMMITTER_NAME=$(git config user.name)" \
  --env "GIT_COMMITTER_EMAIL=$(git config user.email)" \
  --workdir /workspace \
  "$NAME" \
  "${@:-bash}"
