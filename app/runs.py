"""runs.py: scrape and find-emails jobs, started from the app and kept alive without it.

A job is a detached shell process working inside the project folder. It survives the app
closing, writes its own log, and leaves an exit code behind, so the app can always say
honestly what happened: running, done, stopped, or blocked by Google (exit 3, resumable).

Scrapes run one search phrase after another, never in parallel: two scrapers on one
connection is how an address gets blocked. Each finished phrase is ingested straight away,
so leads appear on the board while the next phrase is still running.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
from argparse import Namespace
from pathlib import Path

import store

REPO = Path(__file__).resolve().parent.parent
UV = shutil.which("uv") or "/opt/homebrew/bin/uv"
SAMPLE_POINTS = 4

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind        TEXT,               -- scrape | enrich
    label       TEXT,
    request     TEXT,               -- JSON: what was asked for
    dir         TEXT,               -- folder inside the project
    pid         INTEGER,
    started_at  TEXT,
    stopped     INTEGER DEFAULT 0   -- stopped by hand
);
"""


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:50] or "run"


def _selectors(req: dict) -> list[str]:
    out = []
    for key, flag in (("country", "--country"), ("admin1", "--admin1"), ("near", "--near"), ("radius_km", "--radius-km")):
        if req.get(key) not in (None, ""):
            out += [flag, str(req[key])]
    if req.get("sample"):               # a taste before committing hours: a few searches, no splitting of busy areas
        out += ["--max-points", str(SAMPLE_POINTS), "--max-depth", "0"]
    return out


def plan(req: dict) -> dict:
    """What a scrape would cost, before a single request goes to Google."""
    import world_grid as wg
    phrases = [p.strip() for p in req.get("phrases") or [] if p.strip()]
    if not phrases:
        return {"error": "Type at least one thing to search for, like \"plumbers\"."}
    if not req.get("country"):
        return {"error": "Pick a country."}
    if req.get("near") and not req.get("radius_km"):
        req["radius_km"] = 25
    args = Namespace(country=req["country"], admin1=req.get("admin1") or None, near=req.get("near") or None,
                     radius_km=float(req["radius_km"]) if req.get("radius_km") else None, bbox=None, world=False,
                     min_pop=wg.DEFAULT_MIN_POP, spacing=wg.DEFAULT_SPACING_KM, max_depth=wg.DEFAULT_MAX_DEPTH)
    try:
        seeds = wg.absorb(wg.select_places(args))
    except SystemExit as e:
        return {"error": str(e)}
    points = wg.build_points(seeds, args.spacing)
    dense = sum(len(wg.lattice(s["lat"], s["lng"], s["hw"], args.spacing)) for s in seeds if s["population"] >= 150_000)
    est_points = SAMPLE_POINTS if req.get("sample") else int(len(points) + 0.5 * 4 * dense)
    hours = est_points * wg.SECONDS_PER_POINT_EST / 3600 * len(phrases)
    top = sorted(seeds, key=lambda s: -s["population"])[:8]
    return {"request": {**req, "phrases": phrases, "sample": bool(req.get("sample"))}, "places": len(seeds), "points": len(points), "est_points": est_points,
            "hours": round(hours, 1), "phrases": phrases,
            "biggest": [{"name": s["name"], "population": s["population"]} for s in top],
            "promises": ["Nothing is requested from Google until you confirm.",
                         "One phrase at a time, at a human pace, and it stops by itself if Google pushes back.",
                         "You can stop it and pick it up later without losing anything."]}


def start_scrape(conn, req: dict, resume_id: int | None = None) -> dict:
    conn.executescript(SCHEMA)
    if any(r["state"] == "running" and r["kind"] == "scrape" for r in list_runs(conn)):
        return {"error": "A scrape is already running in this project. One at a time keeps Google from blocking you."}
    if resume_id:
        row = conn.execute("SELECT * FROM runs WHERE id=?", (resume_id,)).fetchone()
        req, rel = json.loads(row["request"]), row["dir"]
    else:
        label = ("Sample: " if req.get("sample") else "") + ", ".join(req["phrases"]) + " · " + (f"{req['near']} {req.get('radius_km')} km" if req.get("near") else req["country"])
        cur = conn.execute("INSERT INTO runs(kind, label, request, started_at) VALUES('scrape', ?, ?, ?)",
                           (label, json.dumps(req), store.iso(store.now_utc())))
        resume_id, rel = cur.lastrowid, f"data/run_{cur.lastrowid}"
    run_dir = store.PROJECT / rel
    run_dir.mkdir(parents=True, exist_ok=True)
    steps = []
    grid, ingest = shlex.quote(str(REPO / "scrape/world_grid.py")), shlex.quote(str(REPO / "leads/pipeline.py"))
    for phrase in req["phrases"]:
        out = f"{rel}/{slug(phrase)}"
        resume = "--resume" if (store.PROJECT / out / "plan.json").exists() else ""
        # The scraper writes its results file even when interrupted, so "finished" is our own marker.
        # Whatever was found is ingested either way: a stopped run still puts its leads on the board.
        steps.append(
            f"if [ ! -f {shlex.quote(out)}/.complete ]; then\n"
            f"  {shlex.quote(UV)} run --script {grid} run {shlex.quote(phrase)} {' '.join(shlex.quote(a) for a in _selectors(req))} "
            f"--out-dir {shlex.quote(out)} --profile {shlex.quote(phrase.title())} {resume}\n"
            f"  code=$?\n"
            f"  for f in {shlex.quote(out)}/*_full.json; do [ -f \"$f\" ] && {shlex.quote(UV)} run --script {ingest} ingest \"$f\"; done\n"
            f"  [ $code -eq 0 ] || exit $code\n"
            f"  touch {shlex.quote(out)}/.complete\n"
            f"fi")
    pid = _spawn(run_dir, "\n".join(steps))
    conn.execute("UPDATE runs SET dir=?, pid=?, stopped=0 WHERE id=?", (rel, pid, resume_id))
    conn.commit()
    return {"id": resume_id}


def start_enrich(conn) -> dict:
    conn.executescript(SCHEMA)
    if any(r["state"] == "running" and r["kind"] == "enrich" for r in list_runs(conn)):
        return {"error": "Already looking for emails in this project."}
    todo = enrich_todo(conn)
    if not todo:
        return {"error": "Every business with a website has already been checked."}
    cur = conn.execute("INSERT INTO runs(kind, label, request, started_at) VALUES('enrich', ?, ?, ?)",
                       (f"Find emails on {todo:,} websites", json.dumps({"todo": todo}), store.iso(store.now_utc())))
    rel = f"data/enrich_{cur.lastrowid}"
    (store.PROJECT / rel).mkdir(parents=True, exist_ok=True)
    pid = _spawn(store.PROJECT / rel,
                 f"{shlex.quote(UV)} run --script {shlex.quote(str(REPO / 'enrich/enrich_websites.py'))} --profile-like '' || exit $?\n"
                 f"{shlex.quote(UV)} run --script {shlex.quote(str(REPO / 'app.py'))} sync --project {shlex.quote(str(store.PROJECT))}")
    conn.execute("UPDATE runs SET dir=?, pid=? WHERE id=?", (rel, pid, cur.lastrowid))
    conn.commit()
    return {"id": cur.lastrowid}


def enrich_todo(conn) -> int:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(businesses)")}
    fresh = "" if "enrich_status" not in cols else " AND (enrich_status IS NULL OR enrich_status = '')"
    return conn.execute("SELECT COUNT(*) FROM businesses WHERE profile IS NOT NULL AND COALESCE(website,'') <> ''" + fresh).fetchone()[0]


def _spawn(run_dir: Path, script: str) -> int:
    (run_dir / "exit_code").unlink(missing_ok=True)
    body = f"cd {shlex.quote(str(store.PROJECT))} || exit 1\n(\n{script}\n)\necho $? > {shlex.quote(str(run_dir / 'exit_code'))}\n"
    log = open(run_dir / "run.log", "ab")
    env = dict(os.environ, PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin", PYTHONUNBUFFERED="1")
    return subprocess.Popen(["/bin/sh", "-c", body], stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                            start_new_session=True, env=env).pid


def _alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def stop(conn, run_id: int) -> dict:
    row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if row and _alive(row["pid"]):
        try:
            os.killpg(int(row["pid"]), signal.SIGINT)      # the scraper saves its place on Ctrl-C
        except OSError:
            pass
    conn.execute("UPDATE runs SET stopped=1 WHERE id=?", (run_id,))
    conn.commit()
    return {"ok": True}


def list_runs(conn) -> list[dict]:
    conn.executescript(SCHEMA)
    out = []
    for r in conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 30"):
        d = dict(r)
        run_dir = store.PROJECT / (r["dir"] or "")
        code_file = run_dir / "exit_code"
        code = int(code_file.read_text().strip() or 1) if r["dir"] and code_file.exists() else None
        d["state"] = ("running" if code is None and _alive(r["pid"]) else "done" if code == 0 else
                      "blocked" if code == 3 else "stopped" if r["stopped"] or code in (130, None) else "failed")
        d["request"] = json.loads(r["request"] or "{}")
        if r["kind"] == "scrape" and r["dir"]:
            d["progress"] = _scrape_progress(run_dir, d["request"].get("phrases") or [])
        log = run_dir / "run.log"
        d["last_line"] = ""
        if r["dir"] and log.exists():
            lines = [ln for ln in log.read_bytes()[-2000:].decode(errors="replace").splitlines() if ln.strip()]
            d["last_line"] = lines[-1][:200] if lines else ""
        out.append(d)
    return out


def _scrape_progress(run_dir: Path, phrases: list[str]) -> dict:
    points_total = points_done = found = 0
    current = None
    for phrase in phrases:
        d = run_dir / slug(phrase)
        try:
            base = len(json.loads((d / "plan.json").read_text())["points"])
            state = json.loads((d / "state.json").read_text()) if (d / "state.json").exists() else {"done": [], "queue": []}
        except (OSError, ValueError):
            continue
        points_done += len(state["done"])
        points_total += max(base, len(state["done"]) + len(state["queue"]))
        with open(d / "results.jsonl", "rb") as fh:
            found += sum(1 for _ in fh)
        if not (d / ".complete").exists():
            current = current or phrase
    if current:                          # the scraper saves its place every 10 searches; its log is up to the second
        log = run_dir / "run.log"
        marks = re.findall(r"\[(\d+)/(\d+)\]", log.read_bytes()[-4000:].decode(errors="replace")) if log.exists() else []
        if marks:
            d = run_dir / slug(current)
            saved = len(json.loads((d / "state.json").read_text())["done"]) if (d / "state.json").exists() else 0
            n, m = int(marks[-1][0]), int(marks[-1][1])
            if n > saved:
                points_done += n - saved
                points_total = max(points_total, points_done - n + m)
    return {"points_done": points_done, "points_total": points_total, "found": found, "phrase": current,
            "phrases_done": sum(1 for p in phrases if (run_dir / slug(p) / ".complete").exists()), "phrases": len(phrases)}
