"""code-map generator — renders docs/code-map.json as interactive HTML."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# Allow `from _shared import …` when invoked via the dispatcher.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from _shared import (
    ROLE_COLORS,
    classify_role,
    default_output,
    ensure_output_dir,
    json_safe,
    project_root,
    read_vendor,
)


GENERATOR_NAME = "code-map"
DESCRIPTION = "Render docs/code-map.json as interactive HTML (modules → files → symbols)."


def _ensure_fresh(json_path: Path, root: Path) -> None:
    """If json_path is missing or stale relative to source files, regenerate it."""
    audit_script = root / "skills" / "audit-code-map" / "Tools" / "code_map.py"
    if not audit_script.exists():
        if not json_path.exists():
            raise FileNotFoundError(
                f"docs/code-map.json not found and audit-code-map script "
                f"missing at {audit_script}. Run /audit-code-map --emit-json first."
            )
        return
    try:
        subprocess.run(
            ["python3", str(audit_script), "--ensure-fresh", "--emit-json",
             "--json-output", str(json_path), "--root", str(root)],
            check=True, capture_output=True, timeout=60,
        )
    except subprocess.SubprocessError as exc:
        if not json_path.exists():
            raise FileNotFoundError(
                f"failed to refresh {json_path}: {exc}"
            ) from exc
        # Stale json is better than no render — continue with what we have.


def _enrich_files(data: dict) -> dict:
    """Add `role` field to each file record using convention classifier."""
    for f in data.get("files", []):
        f["role"] = classify_role(f["path"])
    data["role_colors"] = ROLE_COLORS
    return data


def render(args) -> Path:
    root = project_root()
    input_path: Path = args.input or (root / "docs" / "code-map.json")
    output_path: Path = args.output or default_output("code-map", root)

    _ensure_fresh(input_path, root)

    if not input_path.exists():
        raise FileNotFoundError(
            f"input not found: {input_path}\n"
            f"Run /audit-code-map --emit-json to produce it."
        )

    data = json.loads(input_path.read_text(encoding="utf-8"))

    if data.get("version", 0) < 3:
        raise FileNotFoundError(
            f"{input_path} is schema version {data.get('version')}, need >= 3 "
            f"(file_edges field). Regenerate via /audit-code-map --emit-json."
        )

    data = _enrich_files(data)

    template = (Path(__file__).resolve().parent.parent
                / "templates" / "code-map.html").read_text(encoding="utf-8")

    html = (template
            .replace("__DATA_JSON__", json_safe(data))
            .replace("__CYTOSCAPE_JS__", read_vendor("cytoscape.min.js"))
            .replace("__DAGRE_JS__", read_vendor("dagre.min.js"))
            .replace("__CYTOSCAPE_DAGRE_JS__", read_vendor("cytoscape-dagre.min.js")))

    ensure_output_dir(output_path)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def register():
    return {
        "name": GENERATOR_NAME,
        "description": DESCRIPTION,
        "render": render,
    }
