"""Regression test: TS/TSX symbol extraction must see `export default`.

Next.js App Router declares every page, layout, loading and error boundary as
`export default function X`, and the original patterns had no slot for
`default` between `export` and `function`/`class`. Whole route trees therefore
indexed with zero symbols — the code map looked complete while being blank
exactly where the app lives.

Found as a local fix in a consumer project (8 of 10 such files empty) and
upstreamed 2026-08-02.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "skills" / "audit-code-map" / "Tools" / "code_map.py"

_spec = importlib.util.spec_from_file_location("forge_code_map", MODULE_PATH)
code_map = importlib.util.module_from_spec(_spec)
sys.modules["forge_code_map"] = code_map
_spec.loader.exec_module(code_map)


def _symbols(source: str) -> tuple[list[str], list[str]]:
    """(classes, funcs) as the TS extractor sees them."""
    classes = code_map._TS_CLASS.findall(source)
    funcs = code_map._TS_FUNC.findall(source) + code_map._TS_ARROW.findall(source)
    return classes, funcs


def test_export_default_function_is_indexed():
    """The App Router page/layout shape."""
    _, funcs = _symbols("export default function DashboardPage() {\n  return null\n}\n")
    assert "DashboardPage" in funcs


def test_export_default_async_function_is_indexed():
    """Server components are routinely async."""
    _, funcs = _symbols("export default async function Layout({ children }) {}\n")
    assert "Layout" in funcs


def test_export_default_class_is_indexed():
    _, _ = _symbols("")  # module loaded
    classes, _ = _symbols("export default class ErrorBoundary extends Component {}\n")
    assert "ErrorBoundary" in classes


def test_plain_exports_still_work():
    """The widening must not cost the forms that already worked."""
    classes, funcs = _symbols(
        "export class UserService {}\n"
        "export function helper() {}\n"
        "export async function fetchAll() {}\n"
        "function bare() {}\n"
        "export const Widget = (props) => null\n"
    )
    assert "UserService" in classes
    for name in ("helper", "fetchAll", "bare", "Widget"):
        assert name in funcs, name


def test_default_alone_does_not_invent_symbols():
    """`export default <expr>` has no declared name to index."""
    classes, funcs = _symbols("export default someExistingThing\n")
    assert not classes
    assert not funcs
