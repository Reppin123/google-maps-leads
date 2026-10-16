"""project.py: the line between the product and the work done with it.

This repo is the product: scrape, enrich, leads, outreach. It never holds client
data. A PROJECT is a folder somewhere else with one client's or one campaign's
everything: leads.db, scrape runs, logs, the board, and project.json. Separate
scrapes are separate projects; nothing is ever mixed.

Scrape, enrich and ingest scripts use paths relative to the current folder, so
they are run from inside the project folder. The app takes --project.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULTS = {"name": "", "country": "", "default_tz": "UTC"}


def resolve(arg: str | None = None) -> Path:
    """--project, else $MAPS_LEADS_PROJECT, else the current folder if it is a project."""
    for candidate in (arg, os.environ.get("MAPS_LEADS_PROJECT"), "."):
        if candidate:
            p = Path(candidate).expanduser().resolve()
            if (p / "project.json").exists():
                return p
            if candidate != ".":
                raise SystemExit(f"{p} is not a project (no project.json). Create one with: app.py new-project {p}")
    raise SystemExit("Which project? Pass --project <folder>, or run from inside a project folder.")


def settings(project: Path) -> dict:
    out = dict(DEFAULTS, **json.loads((project / "project.json").read_text()))
    out["name"] = out["name"] or project.name
    return out


def create(folder: str, name: str, country: str, default_tz: str) -> Path:
    p = Path(folder).expanduser().resolve()
    if (p / "project.json").exists():
        raise SystemExit(f"{p} is already a project.")
    for sub in ("data", "logs", "exports"):
        (p / sub).mkdir(parents=True, exist_ok=True)
    (p / "project.json").write_text(json.dumps(
        {"name": name or p.name, "country": country.upper(), "default_tz": default_tz}, indent=1) + "\n")
    board = Path(__file__).resolve().parent / "board"      # every project starts with the standard leads board
    spec = (board / "default_spec.json").read_text().replace("__SLUG__", p.name).replace("__NAME__", name or p.name)
    (p / "dashboard.spec.json").write_text(spec)
    (p / "adapter.py").write_text((board / "default_adapter.py").read_text())
    return p
