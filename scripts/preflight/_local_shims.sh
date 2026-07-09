#!/usr/bin/env bash
# Project-local portability shims for /preflight-ci generated scripts.
#
# This file is sourced by every `.forge/preflight/<job>.sh` before its
# CI-transcribed steps run. It ships empty — extend it when your local
# toolchain differs from the CI runner's.
#
# Common shims:
#
#   # `pip` -> `python3 -m pip` when only pip3 / framework Python is present:
#   command -v pip >/dev/null 2>&1 || pip() { python3 -m pip "$@"; }
#
#   # `python` -> `python3` on systems without the unversioned symlink:
#   command -v python >/dev/null 2>&1 || python() { python3 "$@"; }
#
# Guidelines:
#   1. Idempotent — guard each shim with `command -v <bin> >/dev/null` so
#      it's a no-op when the real binary is on PATH.
#   2. Define functions, not aliases (aliases don't expand in non-interactive
#      shells, which is what preflight scripts run under).
#   3. This file is project-local and survives `install.sh --mode refresh-v3`
#      (the framework will not overwrite an existing copy).
:
