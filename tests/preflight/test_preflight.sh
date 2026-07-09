#!/usr/bin/env bash
# tests/preflight/test_preflight.sh
#
# Single-file probe runner for F-PREFLIGHT-CI ISCs. Each test prints
# "PASS: <isc-id>" or "FAIL: <isc-id> — <reason>". Exits non-zero on any
# failure. Run from repo root.
#
#   bash tests/preflight/test_preflight.sh

set -uo pipefail

FAIL_COUNT=0
PASS_COUNT=0
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

pass() { printf "PASS: %s\n" "$1"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { printf "FAIL: %s — %s\n" "$1" "$2"; FAIL_COUNT=$((FAIL_COUNT+1)); }

# Resolve PYTHON_BIN: prefer the framework-owned .forge/venv/ (it has PyYAML
# installed by venv_manager.ensure_venv). If absent, bootstrap one here so
# the test exercises the same path real consumers take. Bare `python3` is
# the last resort — but a clean Homebrew Python has no PyYAML, so the
# fallback exists only for environments that happen to have PyYAML on
# the system Python (CI containers with apt-installed python3-yaml, etc.).
FORGE_VENV_PY="$REPO_ROOT/.forge/venv/bin/python"
if [[ ! -x "$FORGE_VENV_PY" ]]; then
    echo "test setup: bootstrapping .forge/venv/ via venv_manager …" >&2
    python3 -c "
import sys
sys.path.insert(0, 'scripts/preflight')
from venv_manager import ensure_venv
from pathlib import Path
r = ensure_venv(Path('$REPO_ROOT'))
print(f'  {r.status}: {r.message}', file=sys.stderr)
" 2>&1
fi
if [[ -x "$FORGE_VENV_PY" ]]; then
    PYTHON_BIN="$FORGE_VENV_PY"
else
    PYTHON_BIN="python3"
fi
echo "test setup: PYTHON_BIN=$PYTHON_BIN" >&2

# ------------- ISC-1: skill scaffold -----------------------------------------
if [[ -f skills/preflight-ci/SKILL.md ]] && \
   grep -q "^name: preflight-ci" skills/preflight-ci/SKILL.md && \
   grep -q "Step 1: Locate gating jobs" skills/preflight-ci/SKILL.md && \
   grep -q "Step 5: Route failures" skills/preflight-ci/SKILL.md
then
    pass "ISC-1"
else
    fail "ISC-1" "skill scaffold missing required structure"
fi

# ------------- ISC-2 + ISC-3: workflow parser --------------------------------
WF=/tmp/preflight-iter-workflows
rm -rf "$WF" && mkdir -p "$WF" && cp tests/preflight/fixtures/ci.yml "$WF/"

NAMES_FULL=$(${PYTHON_BIN} scripts/preflight/workflow_parser.py "$WF" --json \
    | ${PYTHON_BIN} -c 'import json,sys; d=json.load(sys.stdin); print(",".join(j["name"] for j in d))')
if [[ "$NAMES_FULL" == "typecheck,test,lint" ]]; then
    pass "ISC-2"
else
    fail "ISC-2" "expected typecheck,test,lint; got '$NAMES_FULL'"
fi

NAMES_NARROW=$(${PYTHON_BIN} scripts/preflight/workflow_parser.py "$WF" \
    --protection-mock tests/preflight/fixtures/protection.json --json \
    | ${PYTHON_BIN} -c 'import json,sys; d=json.load(sys.stdin); print(",".join(j["name"] for j in d))')
if [[ "$NAMES_NARROW" == "typecheck,test" ]]; then
    pass "ISC-3"
else
    fail "ISC-3" "expected typecheck,test; got '$NAMES_NARROW'"
fi

# ------------- ISC-4 + ISC-5: forge task add --preflight ---------------------
SCR=/tmp/preflight-iter-forge
rm -rf "$SCR" && mkdir -p "$SCR/docs/tasks"
cat > "$SCR/docs/tasks/registry.json" <<'JSON'
{"version": "3.0", "epics": [{"id": "E99", "name": "S"}], "tasks": []}
JSON

probe_pf() {
    local id=$1 scope=$2 flag=$3 expected=$4
    local args=(task add "$id" --epic E99 --name "x" --scope-dirs "$scope")
    if [[ -n "$flag" ]]; then args+=(--preflight "$flag"); fi
    args+=(--json)
    local actual
    actual=$(${PYTHON_BIN} scripts/forge/forge.py --project-root "$SCR" "${args[@]}" 2>/dev/null \
        | ${PYTHON_BIN} -c 'import json,sys; print(json.load(sys.stdin).get("preflight_required"))')
    if [[ "$actual" == "$expected" ]]; then
        return 0
    else
        echo "  $id scope=$scope flag=$flag → expected=$expected actual=$actual" >&2
        return 1
    fi
}

# ISC-4: explicit flag values write the right bool
ok=1
probe_pf T-A "src/"   "required" "True"  || ok=0
probe_pf T-B "src/"   "skip"     "False" || ok=0
if [[ "$ok" == "1" ]]; then pass "ISC-4"; else fail "ISC-4" "explicit flag did not record correctly"; fi

# ISC-5: auto-detection table
ok=1
probe_pf T-C "src/"      ""       "True"  || ok=0
probe_pf T-D "docs/"     ""       "False" || ok=0
probe_pf T-E "README.md" ""       "False" || ok=0
probe_pf T-F "docs/,src/" ""      "True"  || ok=0
if [[ "$ok" == "1" ]]; then pass "ISC-5"; else fail "ISC-5" "auto-detect rule wrong on one or more rows"; fi

# ------------- ISC-6: script generation --------------------------------------
GEN=/tmp/preflight-iter-gen
rm -rf "$GEN" && mkdir -p "$GEN"
${PYTHON_BIN} -m scripts.preflight.script_generator "$WF" --out "$GEN" >/dev/null
if [[ -f "$GEN/typecheck.sh" ]] && head -2 "$GEN/typecheck.sh" | grep -q '^#!/usr/bin/env bash' && \
   head -3 "$GEN/typecheck.sh" | grep -q 'set -euo pipefail' && \
   grep -q "npm run type-check" "$GEN/typecheck.sh"
then
    pass "ISC-6"
else
    fail "ISC-6" "typecheck.sh missing expected lines"
fi

# ------------- ISC-7: drift detection ----------------------------------------
DRIFT_BEFORE=$(${PYTHON_BIN} -m scripts.preflight.script_generator "$WF" --out "$GEN" --check-drift; echo $?)
echo '# tweak' >> "$WF/ci.yml"
DRIFT_AFTER=$(${PYTHON_BIN} -m scripts.preflight.script_generator "$WF" --out "$GEN" --check-drift 2>/dev/null; echo $?)
# restore so downstream tests aren't perturbed
cp tests/preflight/fixtures/ci.yml "$WF/ci.yml"
# DRIFT_BEFORE: "✓ No drift\n0"; DRIFT_AFTER ends with "2"
if [[ "$DRIFT_BEFORE" == *"0"* ]] && [[ "$DRIFT_AFTER" == *"2"* ]]; then
    pass "ISC-7"
else
    fail "ISC-7" "drift exit codes wrong (before='$DRIFT_BEFORE' after='$DRIFT_AFTER')"
fi

# ------------- ISC-8: green/red exit codes -----------------------------------
GP=/tmp/preflight-iter-green
rm -rf "$GP" && mkdir -p "$GP/.github/workflows"
cat > "$GP/.github/workflows/ci.yml" <<'YAML'
name: CI
on: { pull_request: { branches: [main] } }
jobs:
  ok:
    runs-on: ubuntu-latest
    steps:
      - run: echo hi
YAML
${PYTHON_BIN} -m scripts.preflight.preflight --project-root "$GP" --regenerate >/dev/null
GREEN_EXIT=$?

RP=/tmp/preflight-iter-red
rm -rf "$RP" && mkdir -p "$RP/.github/workflows"
cat > "$RP/.github/workflows/ci.yml" <<'YAML'
name: CI
on: { pull_request: { branches: [main] } }
jobs:
  bad:
    runs-on: ubuntu-latest
    steps:
      - run: "false"
YAML
${PYTHON_BIN} -m scripts.preflight.preflight --project-root "$RP" --regenerate >/dev/null 2>&1
RED_EXIT=$?

if [[ "$GREEN_EXIT" == "0" && "$RED_EXIT" == "3" ]]; then
    pass "ISC-8"
else
    fail "ISC-8" "green-exit=$GREEN_EXIT red-exit=$RED_EXIT (expected 0 and 3)"
fi

# ------------- ISC-9: hook conditional firing --------------------------------
HOOK_REPO=/tmp/preflight-iter-hook
rm -rf "$HOOK_REPO" && mkdir -p "$HOOK_REPO" && (cd "$HOOK_REPO" && git init -q)
${PYTHON_BIN} scripts/forge/forge.py --project-root "$HOOK_REPO" preflight enable-git-hook >/dev/null
if [[ -x "$HOOK_REPO/.git/hooks/pre-push" ]] && \
   grep -q "FORGE_PREFLIGHT_HOOK_V1" "$HOOK_REPO/.git/hooks/pre-push" && \
   grep -q "task ls --in-progress --json" "$HOOK_REPO/.git/hooks/pre-push" && \
   grep -q "preflight_required" "$HOOK_REPO/.git/hooks/pre-push" && \
   grep -q "preflight.py" "$HOOK_REPO/.git/hooks/pre-push"
then
    pass "ISC-9"
else
    fail "ISC-9" "installed hook missing expected markers"
fi

# ------------- ISC-9b: preflight.py runs as a script (hook's invocation) -----
# Regression guard: the pre-push hook invokes preflight.py as a script, not
# via `python3 -m`. Relative imports inside the file would break that path
# silently — ISC-9 only substring-matches the hook, it does not execute it.
# Probe: actually invoke preflight.py as a bare script and confirm it loads
# its siblings (script_generator, workflow_parser) without ImportError.
if ${PYTHON_BIN} scripts/preflight/preflight.py --help >/dev/null 2>&1 && \
   ${PYTHON_BIN} scripts/preflight/script_generator.py --help >/dev/null 2>&1; then
    pass "ISC-9b"
else
    fail "ISC-9b" "preflight.py or script_generator.py fails to import siblings when run as a script (hook would fail at push time)"
fi

# ------------- ISC-10: shared classifier referenced, not embedded ------------
if [[ -f skills/_shared/ci-failure-classifier.md ]] && \
   grep -q "pr-test-analyzer" skills/_shared/ci-failure-classifier.md && \
   [[ $(grep -c "pr-test-analyzer" skills/diagnose-ci/SKILL.md) == "0" ]] && \
   [[ $(grep -c "pr-test-analyzer" skills/preflight-ci/SKILL.md) == "0" ]]
then
    pass "ISC-10"
else
    fail "ISC-10" "classifier not centralized or skills still embed routing table"
fi

# ------------- ISC-11: disable-git-hook idempotency --------------------------
${PYTHON_BIN} scripts/forge/forge.py --project-root "$HOOK_REPO" preflight disable-git-hook >/dev/null
D1=$?
${PYTHON_BIN} scripts/forge/forge.py --project-root "$HOOK_REPO" preflight disable-git-hook >/dev/null
D2=$?
if [[ "$D1" == "0" && "$D2" == "0" ]] && [[ ! -f "$HOOK_REPO/.git/hooks/pre-push" ]]; then
    pass "ISC-11"
else
    fail "ISC-11" "disable idempotency broken (D1=$D1 D2=$D2)"
fi

# ------------- ISC-12: create-pr Step 3.6 wired ------------------------------
if grep -q "Step 3.6: Preflight CI mirror" skills/create-pr/SKILL.md && \
   grep -q "preflight.py" skills/create-pr/SKILL.md && \
   grep -q "Block PR creation" skills/create-pr/SKILL.md
then
    pass "ISC-12"
else
    fail "ISC-12" "create-pr missing Step 3.6 wiring"
fi

# ------------- ISC-13: CLAUDE.md skills table row ----------------------------
if grep -qE '^\| `/preflight-ci` \|' CLAUDE.md; then
    pass "ISC-13"
else
    fail "ISC-13" "no /preflight-ci row in CLAUDE.md skills table"
fi

# ------------- ISC-14 (anti): no forbidden git/gh push calls -----------------
# Scope is intentionally narrow — executable code only. Documentation (SKILL.md,
# ISA.md) is allowed to *reference* the strings as long as they aren't invoked.
# The pre-push hook template is exempted because its job is to interpose on
# `git push`; the user's git invocation is what triggers it, never the skill.
MATCHES=$(grep -RE "gh run rerun|gh pr (create|edit)|git push" \
    --include='*.py' --include='*.sh' \
    skills/preflight-ci/ scripts/preflight/ 2>/dev/null \
    | grep -vE "^scripts/preflight/pre-push\.template\.sh:" \
    || true)
if [[ -z "$MATCHES" ]]; then
    pass "ISC-14"
else
    fail "ISC-14" "forbidden strings found: $MATCHES"
fi

# ------------- ISC-15: GHA template rewrite (secrets + runnable bash) --------
# script_generator must rewrite `${{ secrets|env|vars|inputs.NAME }}` to
# `${NAME:-}` so generated scripts (a) don't leak the literal `${{ secrets.* }}`
# pattern that trips gitleaks, and (b) are valid bash. Non-target forms
# (github.*, matrix.*, steps.*, function calls, dashed names) pass through
# untouched — verified by absence of regex misfire.
REWRITE_WF=/tmp/preflight-iter-rewrite-wf
REWRITE_OUT=/tmp/preflight-iter-rewrite-out
rm -rf "$REWRITE_WF" "$REWRITE_OUT" && mkdir -p "$REWRITE_WF"
cat > "$REWRITE_WF/ci.yml" <<'YAML'
name: CI
on: { pull_request: { branches: [main] } }
jobs:
  secrets:
    runs-on: ubuntu-latest
    env:
      SECRET_ENCRYPTION_KEY: ${{ secrets.SECRET_ENCRYPTION_KEY }}
      MIXED: "https://${{ secrets.HOST }}/api"
      REF: ${{ github.ref }}
      LITERAL: "p$word"
    steps:
      - name: nested
        env: { STEP_TOKEN: "${{ secrets.STEP_TOKEN }}" }
        run: echo "key=${{ secrets.SECRET_ENCRYPTION_KEY }} step=$STEP_TOKEN"
YAML
${PYTHON_BIN} -m scripts.preflight.script_generator "$REWRITE_WF" --out "$REWRITE_OUT" >/dev/null 2>&1
GEN="$REWRITE_OUT/secrets.sh"
ok=1
# (a) no `${{ secrets.` literal remains (the gitleaks-firing pattern)
grep -q '\${{ secrets\.' "$GEN" && { echo "  literal \${{ secrets.* }} pattern survived in $GEN" >&2; ok=0; }
# (b) script is valid bash
bash -n "$GEN" 2>/dev/null || { echo "  generated script failed bash -n" >&2; ok=0; }
# (c) rewritten forms present
grep -q 'export SECRET_ENCRYPTION_KEY="\${SECRET_ENCRYPTION_KEY:-}"' "$GEN" || { echo "  secrets.X env rewrite missing" >&2; ok=0; }
grep -q 'export MIXED="https://\${HOST:-}/api"' "$GEN" || { echo "  mixed-value rewrite missing" >&2; ok=0; }
grep -q 'key=\${SECRET_ENCRYPTION_KEY:-}' "$GEN" || { echo "  run-line rewrite missing" >&2; ok=0; }
# (d) pass-through preserved for non-target forms
grep -q 'export REF="\\\${{ github.ref }}"' "$GEN" || { echo "  github.ref pass-through broken" >&2; ok=0; }
# (e) literal $ in non-template values still escapes (no regression)
grep -q 'export LITERAL="p\\\$word"' "$GEN" || { echo "  literal-\$ escape regressed" >&2; ok=0; }
if [[ "$ok" == "1" ]]; then pass "ISC-15"; else fail "ISC-15" "GHA template rewrite probe failed"; fi

# ------------- ISC-16: per-step shell isolation (cd does not leak) -----------
# Regression guard for T447: render_script must emit each step in its own
# subshell so `cd` in step N does not change cwd for step N+1. GitHub Actions
# runs each step in a fresh shell; the local mirror must mirror that.
ISO_WF=/tmp/preflight-iter-iso-wf
ISO_OUT=/tmp/preflight-iter-iso-out
rm -rf "$ISO_WF" "$ISO_OUT" && mkdir -p "$ISO_WF" "$ISO_OUT/sub-a" "$ISO_OUT/sub-b"
cat > "$ISO_WF/ci.yml" <<'YAML'
name: CI
on: { pull_request: { branches: [main] } }
jobs:
  iso:
    runs-on: ubuntu-latest
    steps:
      - name: cd into sub-a
        run: |
          cd sub-a
          pwd
      - name: expect repo root again
        run: pwd
      - name: cd into sub-b
        run: |
          cd sub-b
          pwd
YAML
${PYTHON_BIN} -m scripts.preflight.script_generator "$ISO_WF" --out "$ISO_OUT" >/dev/null 2>&1
# script_generator emits a shim-source guard; preflight.py normally writes
# _local_shims.sh into the out dir, but we're invoking script_generator
# directly here, so seed the shim manually.
cp scripts/preflight/_local_shims.sh "$ISO_OUT/_local_shims.sh"
ISO_SCRIPT="$ISO_OUT/iso.sh"
ok=1
bash -n "$ISO_SCRIPT" 2>/dev/null || { echo "  generated script failed bash -n" >&2; ok=0; }
# Run the generated script from $ISO_OUT (which has sub-a/ + sub-b/ children)
# and capture the three `pwd` outputs.
PWD_OUT=$(cd "$ISO_OUT" && bash "$ISO_SCRIPT" 2>/dev/null || true)
EXPECTED_1="$ISO_OUT/sub-a"
EXPECTED_2="$ISO_OUT"
EXPECTED_3="$ISO_OUT/sub-b"
# macOS resolves /tmp -> /private/tmp; normalize both sides.
EXPECTED_1_REAL=$(cd "$EXPECTED_1" && pwd)
EXPECTED_2_REAL=$(cd "$EXPECTED_2" && pwd)
EXPECTED_3_REAL=$(cd "$EXPECTED_3" && pwd)
LINES=($PWD_OUT)
if [[ "${LINES[0]:-}" != "$EXPECTED_1_REAL" ]]; then
    echo "  step 1 pwd: expected=$EXPECTED_1_REAL got=${LINES[0]:-<empty>}" >&2
    ok=0
fi
if [[ "${LINES[1]:-}" != "$EXPECTED_2_REAL" ]]; then
    echo "  step 2 pwd: expected=$EXPECTED_2_REAL (repo root, cd should not have leaked) got=${LINES[1]:-<empty>}" >&2
    ok=0
fi
if [[ "${LINES[2]:-}" != "$EXPECTED_3_REAL" ]]; then
    echo "  step 3 pwd: expected=$EXPECTED_3_REAL got=${LINES[2]:-<empty>}" >&2
    ok=0
fi
if [[ "$ok" == "1" ]]; then pass "ISC-16"; else fail "ISC-16" "per-step shell isolation broken — cd leaks across steps"; fi

echo
echo "----- Result -----"
echo "PASS: $PASS_COUNT   FAIL: $FAIL_COUNT"
exit $FAIL_COUNT
