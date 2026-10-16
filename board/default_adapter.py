"""adapter.py: this project's leads.db -> rows for the leads board. Read-only on the store.
Every new project starts with this file; edit it freely, it belongs to the project."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path


def load_rows(project_dir: Path):
    db = sqlite3.connect(f"file:{project_dir / 'leads.db'}?mode=ro", uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    raw = [dict(r) for r in db.execute("SELECT * FROM businesses")]
    pulled = db.execute("SELECT MIN(pulled_at), MAX(pulled_at) FROM pulls_log").fetchone()
    country = json.loads((project_dir / "project.json").read_text()).get("country", "")
    try:                                    # inside the app: region from coordinates, and what each lead has been sent
        import geo, store
        outreach = store.outreach_by_place(db)
    except (ImportError, sqlite3.OperationalError):
        geo, outreach = None, {}
    db.close()
    derived = 0
    for r in raw:
        r["state_derived"] = 0
        if geo and not r.get("state"):
            s = geo.state_from_coords(country, r.get("lat"), r.get("lng"))
            if s:
                r["state"], r["state_derived"] = s, 1
                derived += 1
        o = outreach.get(r["place_id"])
        if o:
            r.update(outreach=o["status"], campaign=o["campaign"], emails_sent=o["emails_sent"], last_email_at=o["last_email_at"])
    meta = {"source": "leads.db", "pulled_min": pulled[0], "pulled_max": pulled[1],
            "notes": [f"region filled from coordinates for {derived:,} rows"] if derived else []}
    return raw, meta
