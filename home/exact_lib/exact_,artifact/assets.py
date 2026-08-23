from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from paths import _read_json, canonical_context_path, sanitize_name

AMBIENT_THEME_STYLE_ID = "agent-artifact-ambient-theme"
ASSET_DIR = Path(__file__).resolve().parent
ASSET_TYPES = {
    "chrome.css": "text/css; charset=utf-8",
    "chrome.js": "application/javascript; charset=utf-8",
    "starter.css": "text/css; charset=utf-8",
}


def asset_text(name: str) -> str:
    return (ASSET_DIR / name).read_text(encoding="utf-8")


def render_asset(name: str, replacements: dict[str, str]) -> str:
    text = asset_text(name)
    for marker, value in replacements.items():
        text = text.replace(marker, value)
    return text


def ambient_theme_catalog() -> dict[str, Any]:
    value = json.loads(asset_text("ambient_themes.json"))
    if not isinstance(value, dict):
        raise ValueError("ambient_themes.json must contain an object")
    return value


def ambient_theme_from_catalog(
    catalog: dict[str, Any],
    name: str,
    project_root: Path,
    markers: list[str] | None = None,
) -> dict[str, Any]:
    theme = catalog.get(name) or catalog["neutral"]
    default_markers = theme.get("markers", [])
    return {
        "name": name,
        "label": str(theme["label"]),
        "root": str(project_root),
        "markers": markers if markers is not None else list(default_markers),
        "tokens": dict(theme["tokens"]),
    }


def detect_ambient_theme(root: Path | None = None) -> dict[str, Any]:
    """Infer a small style vocabulary from broad worktree markers."""

    project_root = root or canonical_context_path(Path.cwd())
    catalog = ambient_theme_catalog()
    package_json = _read_json(project_root / "package.json")
    package_keys: set[str] = set()
    if package_json:
        for field in ("dependencies", "devDependencies", "peerDependencies"):
            value = package_json.get(field)
            if isinstance(value, dict):
                package_keys.update(value)

    if (project_root / ".mermaids").is_dir() and (project_root / "home").is_dir():
        return ambient_theme_from_catalog(catalog, "dotfiles", project_root)
    if (project_root / "docusaurus.config.js").exists() or (project_root / "website").is_dir():
        return ambient_theme_from_catalog(catalog, "docs", project_root)
    if package_keys.intersection({"react", "vue", "svelte", "next", "vite", "@vitejs/plugin-react"}):
        return ambient_theme_from_catalog(catalog, "web-app", project_root)

    codebase_markers = [
        marker for marker in ("go.mod", "Cargo.toml", "pyproject.toml") if (project_root / marker).exists()
    ]
    if codebase_markers:
        return ambient_theme_from_catalog(catalog, "codebase", project_root, codebase_markers)

    return ambient_theme_from_catalog(catalog, "neutral", project_root)


def ambient_theme_style(theme: dict[str, Any] | None = None) -> str:
    """Return a low-specificity CSS layer for agent-authored artifacts."""

    selected = theme or detect_ambient_theme()
    tokens = selected["tokens"]
    css = render_asset(
        "ambient_theme.css",
        {
            "__AA_BG__": str(tokens["bg"]),
            "__AA_SURFACE__": str(tokens["surface"]),
            "__AA_SURFACE_2__": str(tokens["surface_2"]),
            "__AA_INK__": str(tokens["ink"]),
            "__AA_MUTED__": str(tokens["muted"]),
            "__AA_LINE__": str(tokens["line"]),
            "__AA_ACCENT__": str(tokens["accent"]),
            "__AA_ACCENT_2__": str(tokens["accent_2"]),
            "__AA_CODE_BG__": str(tokens["code_bg"]),
        },
    )
    name = html.escape(str(selected["name"]), quote=True)
    return f'<style id="{AMBIENT_THEME_STYLE_ID}" data-theme="{name}">\n{css}\n</style>\n'


def inject_ambient_theme(content: str) -> str:
    if AMBIENT_THEME_STYLE_ID in content:
        return content
    style = ambient_theme_style()
    if re.search(r"</head\s*>", content, flags=re.I):
        return re.sub(r"</head\s*>", lambda _: style + "</head>", content, count=1, flags=re.I)
    return style + content


def starter_html(title: str) -> str:
    safe = html.escape(title, quote=True)
    return render_asset("starter.html", {"__TITLE__": safe})


def inject_client_script(content: str) -> str:
    script = "\n<script>\n" + asset_text("generated_client.js") + "\n</script>\n"
    if re.search(r"</body\s*>", content, flags=re.I):
        return re.sub(r"</body\s*>", lambda _: script + "</body>", content, count=1, flags=re.I)
    return content + script


def chrome_page(name: str) -> str:
    safe_name = sanitize_name(name)
    return render_asset(
        "chrome.html",
        {
            "__ARTIFACT_TITLE__": html.escape(safe_name, quote=True),
            "__ARTIFACT_PATH__": html.escape(safe_name, quote=True),
            "__ARTIFACT_NAME_JSON__": json.dumps(safe_name),
        },
    )
