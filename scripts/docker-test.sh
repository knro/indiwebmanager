#!/bin/bash
# Run tests in Docker as current user so htmlcov/ is owned by you, not root.
cd "$(dirname "$0")/.."
DOCKER_UID=$(id -u) DOCKER_GID=$(id -g) docker compose run --rm --remove-orphans test "$@"
