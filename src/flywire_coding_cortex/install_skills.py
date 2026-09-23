"""Copy bundled skill into Cursor / OpenClaw / Claude skill directories."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .paths import bundled_skill_dir, home


def _cursor_skills() -> Path:
    return Path.home() / ".cursor" / "skills" / "flywire-coding-cortex"


def _openclaw_skills() -> list[Path]:
    h = Path.home()
    return [
        h / ".openclaw" / "workspace" / "skills" / "flywire-coding-cortex",
        h / ".openclaw" / "skills" / "flywire-coding-cortex",
    ]


def _claude_skills() -> Path:
    return Path.home() / ".claude" / "skills" / "flywire-coding-cortex"


def _copy_skill(dest: Path) -> str:
    src = bundled_skill_dir()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    return str(dest)


def mcp_snippet() -> dict[str, Any]:
    return {
        "mcpServers": {
            "flywire-coding-cortex": {
                "command": "flywire-cortex",
                "args": ["mcp"],
            }
        }
    }


def install_all(targets: list[str] | None = None) -> dict[str, Any]:
    targets = targets or ["cursor", "openclaw", "claude"]
    result: dict[str, Any] = {"installed": [], "skipped": [], "mcp": mcp_snippet(), "home": str(home())}
    if "cursor" in targets:
        result["installed"].append({"target": "cursor", "path": _copy_skill(_cursor_skills())})
    if "openclaw" in targets:
        # prefer workspace path; also try top-level skills
        paths = _openclaw_skills()
        primary = paths[0]
        result["installed"].append({"target": "openclaw", "path": _copy_skill(primary)})
        # second path as optional mirror if parent exists
        if paths[1].parent.exists() or paths[1].parent.parent.exists():
            try:
                paths[1].parent.mkdir(parents=True, exist_ok=True)
                result["installed"].append({"target": "openclaw-alt", "path": _copy_skill(paths[1])})
            except OSError as exc:
                result["skipped"].append({"target": "openclaw-alt", "error": str(exc)})
    if "claude" in targets:
        result["installed"].append({"target": "claude", "path": _copy_skill(_claude_skills())})
    tip = home() / "mcp.snippet.json"
    tip.write_text(json.dumps(mcp_snippet(), indent=2) + "\n", encoding="utf-8")
    result["mcp_snippet_file"] = str(tip)
    result["hint"] = (
        "Add the mcp snippet to Cursor MCP settings, then restart the agent session. "
        "Ensure `flywire-cortex` is on PATH (pip/uv install)."
    )
    return result
