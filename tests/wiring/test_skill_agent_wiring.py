"""Static-analysis tests for the skill -> framework-agent wiring graph.

Closes ISC-28: verifies that every Task(subagent_type=...) call in the
B7-wired skills cites a real framework agent, that each agent has the
expected frontmatter shape, and that bound validators exist.

These are not runtime tests — they don't invoke Claude Code or actually
fire any hook. They prove the wiring graph is internally consistent at
write-time, which is the gate that B7's commits passed by inspection.
The tests automate that inspection so future skill edits can't silently
break the graph.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"
AGENTS_DIR = REPO_ROOT / "agents"
VALIDATORS_DIR = REPO_ROOT / "hooks" / "validators" / "agents"

# Skills wired with real Task(subagent_type=...) calls. Every entry must
# fire at least one framework agent (asserted per-skill below) — no count
# floor; v4 removed numeric floors as padding engines.
WIRED_SKILLS = [
    "new-project",
    "new-feature",
    "fix-bug",
    "create-pr",
]

# v3 framework-agent roster (B4.1). Anything else cited as subagent_type
# in a wired skill is a wiring error — either a typo or a leftover cut
# agent that survived B7's re-mapping pass.
FRAMEWORK_AGENTS = {
    "architect",
    "project-manager",
    "quality-engineer",
    "security-boss",
    "devops",
}

# subagent_type values that are intentionally NOT framework agents.
# `general-purpose` is Claude Code's built-in generic subagent, used by
# run-epic's parallel dispatch (skills/run-epic/PARALLEL.md).
BUILTIN_SUBAGENTS = {"general-purpose"}

# Frontmatter parser — minimal, doesn't pull in PyYAML.
# Returns dict[str, str|list] from the leading --- block.
SUBAGENT_RE = re.compile(r'subagent_type:\s*"([^"]+)"')
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    """Minimal frontmatter parser. Handles top-level scalar keys.

    Skips nested structures (hooks: block) — for those we just check
    presence by string search elsewhere.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip()
    return out


def collect_subagent_calls(skill_dir: Path) -> list[tuple[Path, int, str]]:
    """Return [(file, line_number, subagent_type_value), ...] for every
    `subagent_type: "..."` reference inside the skill directory.
    """
    out = []
    for md in sorted(skill_dir.rglob("*.md")):
        for n, line in enumerate(md.read_text().splitlines(), 1):
            for match in SUBAGENT_RE.finditer(line):
                out.append((md, n, match.group(1)))
    return out


# --- Tests --------------------------------------------------------------


@pytest.mark.parametrize("skill", WIRED_SKILLS)
def test_skill_has_at_least_one_framework_agent_call(skill):
    """Each B7-wired skill has at least one Task() block citing a v3
    framework agent (not just general-purpose / template placeholder)."""
    skill_dir = SKILLS_DIR / skill
    assert skill_dir.is_dir(), f"missing skill dir: {skill_dir}"
    calls = collect_subagent_calls(skill_dir)
    framework_calls = [v for _, _, v in calls if v in FRAMEWORK_AGENTS]
    assert framework_calls, (
        f"skill {skill!r} has no Task(subagent_type=...) call referencing "
        f"a framework agent. all calls: {[v for _, _, v in calls]}"
    )


@pytest.mark.parametrize("skill", WIRED_SKILLS)
def test_skill_subagent_calls_resolve_to_real_agents(skill):
    """Every subagent_type in a wired skill refers to either a real
    framework agent (file present at agents/<name>.md) or a known
    Claude Code builtin or a documented template placeholder.
    """
    skill_dir = SKILLS_DIR / skill
    calls = collect_subagent_calls(skill_dir)
    invalid: list[tuple[Path, int, str]] = []
    for md, n, value in calls:
        if value in BUILTIN_SUBAGENTS:
            continue
        # Template placeholders inside example/wiring blocks are valid
        # (they're literal docstring shape, not real wiring).
        if value.startswith("<") and value.endswith(">"):
            continue
        if value in FRAMEWORK_AGENTS:
            agent_path = AGENTS_DIR / f"{value}.md"
            if not agent_path.is_file():
                invalid.append((md, n, value))
            continue
        # Anything else is a wiring error — either a typo or a leftover
        # cut-v2 agent that survived B7's re-mapping pass.
        invalid.append((md, n, value))
    assert not invalid, (
        f"skill {skill!r} has invalid subagent_type calls (cut agent? typo?): "
        + "\n  ".join(f"{p.relative_to(REPO_ROOT)}:{n} -> {v!r}" for p, n, v in invalid)
    )


@pytest.mark.parametrize("agent_name", sorted(FRAMEWORK_AGENTS))
def test_agent_has_required_frontmatter(agent_name):
    """Each framework agent has parseable frontmatter with required keys."""
    agent_path = AGENTS_DIR / f"{agent_name}.md"
    assert agent_path.is_file(), f"missing agent: {agent_path}"
    fm = parse_frontmatter(agent_path.read_text())
    for key in ("name", "description", "model"):
        assert key in fm, f"agent {agent_name} missing frontmatter key {key!r}; got {list(fm)}"
    assert fm["name"] == agent_name, (
        f"agent file {agent_path.name} declares name={fm['name']!r}; "
        f"file basename and frontmatter name must match"
    )


# Per inventory: project-manager has no validator binding; the other 4
# bind to specific files in hooks/validators/agents/.
EXPECTED_VALIDATOR_BINDINGS = {
    "architect": ["architect_adr.py"],
    "project-manager": [],
    "quality-engineer": ["quality_coverage.py", "tdd_aaa.py"],
    "security-boss": ["security_secrets.py"],
    "devops": ["build_deps.py"],
}


@pytest.mark.parametrize("agent_name", sorted(FRAMEWORK_AGENTS))
def test_agent_validator_binding_files_exist(agent_name):
    """Every validator path declared in an agent's hooks: frontmatter
    block resolves to a real file in hooks/validators/agents/.

    For project-manager (no binding), this test passes vacuously.
    """
    agent_path = AGENTS_DIR / f"{agent_name}.md"
    text = agent_path.read_text()
    expected = EXPECTED_VALIDATOR_BINDINGS[agent_name]

    if not expected:
        # project-manager: no hooks: block expected
        assert "validators/agents/" not in text, (
            f"agent {agent_name} unexpectedly cites a validator binding"
        )
        return

    for validator_filename in expected:
        validator_path = VALIDATORS_DIR / validator_filename
        assert validator_path.is_file(), (
            f"agent {agent_name} declares binding to {validator_filename} "
            f"but the file is missing at {validator_path}"
        )
        # The agent file must reference this validator path explicitly.
        assert validator_filename in text, (
            f"agent {agent_name} expected to bind {validator_filename} "
            f"per inventory but the path is not in the agent body"
        )


def test_no_cut_v2_agents_referenced_in_wired_skills():
    """No skill in the wired set should still reference a v2 cut agent
    via subagent_type. Historical 'v2 used X' notes in prose are fine —
    they're documentation, not wiring.
    """
    cut_agents = {
        "analyst", "api-tester", "build-resolver", "doc-updater",
        "e2e-runner", "orchestrator", "performance-enhancer",
        "refactor-cleaner", "scrum-master", "tdd-guide", "ux-designer",
        "visual-mistro", "whimsy",
    }
    leaks: list[tuple[Path, int, str]] = []
    for skill in WIRED_SKILLS:
        for md, n, value in collect_subagent_calls(SKILLS_DIR / skill):
            if value in cut_agents:
                leaks.append((md, n, value))
    assert not leaks, (
        "wired skill still cites a cut v2 agent in a subagent_type call:\n  "
        + "\n  ".join(f"{p.relative_to(REPO_ROOT)}:{n} -> {v!r}" for p, n, v in leaks)
    )
