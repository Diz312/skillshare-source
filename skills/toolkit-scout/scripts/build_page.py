#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Render site/index.html from the catalog, local skills and reports/latest.json.

Usage: build_page.py [--repo-url URL] [--catalog-ref origin/main]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

SKILL_DIR = Path(__file__).resolve().parents[1]
REPO = SKILL_DIR.parents[1]
TEMPLATE = SKILL_DIR / "assets/page.html"
OUT = REPO / "site/index.html"


CATALOG_REF: str | None = None  # read catalog/*.yaml from this git ref instead of the work tree


def _items(path: Path, key: str) -> list[dict[str, Any]]:
    if CATALOG_REF:
        rel = path.relative_to(REPO).as_posix()
        res = subprocess.run(
            ["git", "-C", str(REPO), "show", f"{CATALOG_REF}:{rel}"],
            capture_output=True,
            text=True,
            check=False,
        )
        text = res.stdout if res.returncode == 0 else ""
    elif path.is_file():
        text = path.read_text()
    else:
        return []
    return list((yaml.safe_load(text) or {}).get(key) or [])


def frontmatter(skill_md: Path) -> dict[str, Any]:
    m = re.match(r"\A---\n(.*?)\n---", skill_md.read_text(), re.S)
    return dict(yaml.safe_load(m.group(1)) or {}) if m else {}


def installed(repo: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for s in _items(repo / "catalog/skills.yaml", "skills"):
        out.append(
            {
                "kind": "skill",
                "name": s["name"],
                "category": s.get("category", ""),
                "description": s.get("description", ""),
                "why": s.get("why", ""),
                "source_url": f"https://github.com/{s['repo']}/tree/{s['ref']}/{s.get('path', '')}",
                "pin": f"{s['repo']}@{s['ref'][:7]}",
                "origin": "upstream",
            }
        )
    local = repo / "local-skills"
    for d in sorted(local.iterdir()) if local.is_dir() else []:
        if (d / "SKILL.md").is_file():
            fm = frontmatter(d / "SKILL.md")
            out.append(
                {
                    "kind": "skill",
                    "name": fm.get("name", d.name),
                    "category": fm.get("category", ""),
                    "description": fm.get("description", ""),
                    "origin": "local",
                }
            )
    for m in _items(repo / "catalog/mcp.yaml", "mcp"):
        pin = m.get("url") or " ".join([m.get("command", ""), *m.get("args", [])]).strip()
        secrets = sorted(
            set(re.findall(r"\$\{([A-Z0-9_]+)", json.dumps([m.get("env"), m.get("headers")])))
        )
        out.append(
            {
                "kind": "mcp",
                "name": m["name"],
                "category": m.get("category", ""),
                "description": m.get("description", ""),
                "why": m.get("why", ""),
                "source_url": m.get("source", ""),
                "pin": pin,
                "needs": ", ".join(secrets),
            }
        )
    for p in _items(repo / "catalog/plugins.yaml", "plugins"):
        out.append(
            {
                "kind": "plugin",
                "name": p["name"],
                "category": p.get("category", ""),
                "description": p.get("description", ""),
                "why": p.get("why", ""),
                "source_url": p.get("source", f"https://github.com/{p.get('marketplace', '')}"),
                "harness": p.get("harness", "claude-code"),
                "pin": f"{p['plugin']}@{p['marketplace_name']}",
            }
        )
    return out


def build(repo: Path = REPO, repo_url: str = "") -> dict[str, Any]:
    latest_file = repo / "reports/latest.json"
    latest: dict[str, Any] = json.loads(latest_file.read_text()) if latest_file.is_file() else {}
    prefs = yaml.safe_load((repo / "config/preferences.yaml").read_text()) or {}
    return {
        "generated_at": latest.get("generated_at", ""),
        "summary": latest.get("summary", "No scout run yet."),
        "pr_url": latest.get("pr_url", ""),
        "repo_url": repo_url,
        "categories": list((prefs.get("categories") or {}).keys()),
        "installed": installed(repo),
        "candidates": latest.get("candidates", []),
        "updates": latest.get("updates", []),
    }


def render(data: dict[str, Any], template: Path = TEMPLATE) -> str:
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return template.read_text().replace("/*__DATA__*/null", payload, 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-url", default="")
    ap.add_argument("--catalog-ref", help="show the catalog as of this git ref (e.g. origin/main)")
    args = ap.parse_args(argv)
    global CATALOG_REF
    CATALOG_REF = args.catalog_ref
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(build(REPO, args.repo_url)))
    print(OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
