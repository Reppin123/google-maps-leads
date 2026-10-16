"""server.py: the app. One process serves every project: `/` is the home screen, and everything
about one project lives under `/p/<project folder name>/`. Binds to 127.0.0.1 only; every
write is a JSON POST that must come from the app's own pages."""
from __future__ import annotations

import json
import random
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import ask
import health
import looks
import mailer
import project as projects
import runs
import store

PANEL = Path(__file__).with_name("panel.html")
HOME = Path(__file__).with_name("home.html")
import kit  # noqa: E402  (the leads board module; app.py put board/ on the path)

NAV = [("Ask", "/#/ask"), ("Leads", "/leads"), ("Find leads", "/#/find"), ("Campaigns", "/#/"), ("Replies", "/#/inbox"),
       ("Inboxes", "/#/mailbox"), ("Do not contact", "/#/dnc")]
_board_cache: dict[str, dict] = {}       # per project
_board_lock = threading.Lock()
_migrated: set[str] = set()


def base() -> str:
    return f"/p/{store.PROJECT.name}"


def enter(slug: str) -> bool:
    """Point this request at one project. False when there is no such project."""
    path = next((p for p in store.list_projects() if p.name == slug), None)
    if not path:
        return False
    store.use(path)
    if slug not in _migrated:
        conn = store.connect()
        store.migrate(conn)
        conn.close()
        _migrated.add(slug)
    return True


def board_page() -> bytes:
    """The leads board, built from the project database with stages from the database. Rebuilt only
    when the database has changed since the last look."""
    with _board_lock:
        conn = store.connect()
        # Rebuild only when something the board shows has changed. The file's modified time is no
        # good for this: the background mailbox check writes a timestamp every two minutes.
        stamp = tuple(conn.execute(q).fetchone() for q in (
            "SELECT COUNT(*), MAX(last_seen) FROM businesses", "SELECT COUNT(*), MAX(updated_at) FROM board_annotations",
            "SELECT COUNT(*), MAX(id) FROM out_events", "SELECT COUNT(*) FROM out_enrollments",
            "SELECT COUNT(*) FROM out_contacts")) + (        # find-emails ends by refreshing contacts
            (store.PROJECT / "dashboard.spec.json").stat().st_mtime_ns,)
        cache = _board_cache.setdefault(store.PROJECT.name, {"stamp": None, "html": b""})
        if cache["stamp"] == stamp:
            conn.close()
        else:
            try:
                store.import_board_file(conn)
                spec = kit.load_spec(store.PROJECT)
                ann = store.board_annotations(conn, spec.get("pipeline") or [], spec.get("closed_stages") or [],
                                              spec.get("auto_stages") or {})
            finally:
                conn.close()
            host = {"project": store.CONF["name"], "home": "/", "save_url": base() + "/api/board/annotation",
                    "campaign_url": base() + "/api/campaign/from-leads",
                    "nav": [{"label": label, "href": base() + href, "on": href == "/leads"} for label, href in NAV]}
            cache.update(stamp=stamp, html=kit.build(store.PROJECT, quiet=True, host=host,
                                                                     annotations=ann).encode())
        return cache["html"]


def save_annotation(conn, body) -> dict:
    store.save_annotation(conn, body["id"], body["annotation"])
    return {"ok": True}


def campaign_from_leads(conn, body) -> dict:
    ids = body.get("ids") or []
    out = store.pick_for_campaign(conn, ids, f"{len(ids):,} leads picked on the board")
    return out if out.get("error") else {**out, "href": f"{base()}/#/c/{out['id']}"}


def inbox(conn, _q) -> dict:
    """Every reply, unsubscribe and bounce across all campaigns, newest first."""
    return {"rows": [dict(r) for r in conn.execute(
        "SELECT v.id, v.kind, v.at, v.detail, v.step_position, e.id enrollment_id, e.arm, e.outcome, c.email, b.name, "
        " k.id campaign_id, k.name campaign FROM out_events v JOIN out_enrollments e ON e.id=v.enrollment_id "
        "JOIN out_contacts c ON c.id=e.contact_id JOIN businesses b ON b.place_id=c.place_id "
        "JOIN out_campaigns k ON k.id=e.campaign_id WHERE v.kind IN ('reply','unsubscribe','bounce_hard','auto_reply') "
        "ORDER BY v.at DESC, v.id DESC LIMIT 300")]}


def _inboxes(conn) -> list[dict]:
    """Every inbox with what a person needs to know about it: can it send, how much room today, what is wrong."""
    now, out = store.now_utc(), []
    for mb in store.mailboxes(conn):
        d = {k: mb[k] for k in ("id", "email", "from_name", "provider", "smtp_host", "smtp_port", "imap_host", "imap_port", "signature",
                                "daily_cap", "ramp_start", "ramp_step", "gap_min", "gap_max", "status", "status_reason",
                                "resume_at", "slow_until", "last_watch", "health_at")}
        d["has_password"] = bool(mailer.load_password(mb["email"]))
        d["room"] = store.mailbox_capacity(conn, mb, now)
        d["health"] = json.loads(mb["health"] or "{}")
        d["held"] = conn.execute("SELECT COUNT(*) FROM out_enrollments WHERE mailbox_id=? AND status='active'", (mb["id"],)).fetchone()[0]
        out.append(d)
    return out


def _public_settings(conn) -> dict:
    s = {k: v for k, v in store.get_settings(conn).items() if k in ("footer", "unsub_line", "bounce_pause_pct", "paused_reason", "last_error")}
    boxes = _inboxes(conn)
    s["has_password"] = any(b["has_password"] and b["status"] != "broken" for b in boxes)     # "can anything send?"
    s["from_email"] = ", ".join(b["email"] for b in boxes)
    return s


def state(conn, _q) -> dict:
    s = _public_settings(conn)
    boxes = _inboxes(conn)
    return {
        "settings": s,
        "inboxes": boxes,
        "campaigns": store.summaries(conn),
        "trades": [dict(r) for r in conn.execute("SELECT trade name, COUNT(*) n FROM out_contacts WHERE check_status='ok' "
                                                 "AND trade IS NOT NULL GROUP BY trade ORDER BY n DESC")],
        "states": [dict(r) for r in conn.execute("SELECT state name, COUNT(*) n FROM out_contacts WHERE check_status='ok' "
                                                 "AND state IS NOT NULL GROUP BY state ORDER BY n DESC")],
        "contacts": {r[0]: r[1] for r in conn.execute("SELECT check_status, COUNT(*) FROM out_contacts GROUP BY 1")},
        "capacity": {"cap_today": sum(b["room"]["cap"] for b in boxes if b["status"] in ("active", "resting")),
                     "sent_24h": sum(b["room"]["sent_24h"] for b in boxes)},
        "dnc_count": conn.execute("SELECT COUNT(*) FROM out_suppressed").fetchone()[0],
        "fields": store.FIELDS,
        "schedule_on": mailer.plist_path().exists(),
        "has_board": (store.PROJECT / "dashboard.spec.json").exists(),
        "project": store.CONF["name"],
        "has_ai_key": bool(ask.load_key()),
    }


def campaign(conn, q) -> dict:
    cid = int(q["id"])
    camp = store.load_campaign(conn, cid)
    s = _public_settings(conn)
    camp["preflight"] = store.preflight(conn, camp, store.get_settings(conn), s["has_password"])
    camp["field_usage"] = store.field_usage(conn, camp) if camp["status"] == "draft" else []
    camp["numbers"] = store.version_numbers(conn, cid)
    if camp["status"] != "draft":
        camp["results"] = store.results(conn, cid)
        camp["still_waiting"] = store.waiting(conn, cid) if camp["status"] in ("active", "paused") else 0
    return camp


def audience(conn, body) -> dict:
    aud = store.audience(conn, body.get("filters") or {}, body.get("campaign_id"))
    ids = [r["id"] for r in aud["rows"]]
    random.Random(1).shuffle(ids)                         # a steady order, so "lead 3 of 200" means the same lead twice
    sample = []
    for cid in ids[:6]:
        v = store.merge_values(conn, cid)
        sample.append({"contact_id": cid, "name": v["name"], "suburb": v["suburb"], "state": v["state"], "trade": v["trade"]})
    gaps = [int(g) for g in body.get("gaps") or []]
    return {"matched": aud["matched"], "count": aud["count"], "excluded": aud["excluded"], "sample": sample, "ids": ids[:200],
            "forecast": store.forecast(store.total_pace(conn), aud["count"], gaps, 0, body.get("weekdays") or "1,2,3,4,5")
            if aud["count"] else None}


def preview(conn, body) -> dict:
    """Exactly what one real lead would receive: both parts, the inbox row, and plain advice about the draft."""
    cid = body.get("contact_id")
    if not cid:
        rows = store.audience(conn, body.get("filters") or {}, body.get("campaign_id"))["rows"]
        if not rows:
            return {"error": "Nobody matches this audience yet."}
        cid = random.choice(rows)["id"]
    values = store.merge_values(conn, cid)
    subject, m1 = store.render(body.get("subject") or "", values)
    text, m2 = store.render(body.get("body") or "", values)
    s = store.get_settings(conn)
    boxes = store.mailboxes(conn)
    mb = boxes[0] if boxes else {"from_name": "", "email": "you@yourdomain", "signature": "[your signature]"}
    position, same_thread = int(body.get("position") or 1), bool(body.get("same_thread", 1))
    look = "light" if body.get("look") == "light" and not (position == 1 and body.get("first_plain", 1)) else "plain"
    plain, page = looks.render_parts(text, mb["signature"] or "", s["footer"].strip() or "[your business details]", s["unsub_line"], look)
    to = conn.execute("SELECT email FROM out_contacts WHERE id=?", (cid,)).fetchone()["email"]
    first_line = next((ln.strip() for ln in plain.splitlines() if ln.strip()), "")
    return {"to": to, "contact_id": cid, "subject": subject, "missing": sorted(set(m1 + m2)), "values": values,
            "thread_subject": store.render(body.get("first_subject") or "", values)[0], "text": plain, "html": page, "look": look, "from_name": mb["from_name"] or mb["email"], "from_email": mb["email"],
            "first_line": first_line[:110], "hints": looks.hints(body.get("subject") or "", body.get("body") or "", position, same_thread)}


def save_settings(conn, body) -> dict:
    values = {k: body[k] for k in ("footer", "unsub_line", "bounce_pause_pct") if k in body}
    if "bounce_pause_pct" in values:
        values["bounce_pause_pct"] = float(values["bounce_pause_pct"])
    store.set_settings(conn, values)
    return {"ok": True}


def inbox_save(conn, body) -> dict:
    """Add an inbox or change one. The password goes to the Keychain, never to the database."""
    email_addr = (body.get("email") or "").strip().lower()
    numbers = {k: (float(body[k]) if k in ("gap_min", "gap_max") else int(body[k])) for k in
               ("smtp_port", "imap_port", "daily_cap", "ramp_start", "ramp_step", "gap_min", "gap_max") if body.get(k) not in (None, "")}
    values = {**{k: body[k] for k in ("from_name", "provider", "smtp_host", "imap_host", "signature") if k in body}, **numbers}
    if body.get("id"):
        mid = int(body["id"])
        store.update_mailbox(conn, mid, values)
        email_addr = conn.execute("SELECT email FROM out_mailboxes WHERE id=?", (mid,)).fetchone()["email"]
    else:
        if not store.EMAIL_RE.match(email_addr):
            return {"error": "That does not look like an email address."}
        if body.get("provider") == "microsoft":
            return {"error": "Microsoft 365 and Outlook mailboxes cannot be read with a password any more (Microsoft turned that off in "
                             "2022). They need a Microsoft sign-in, which this tool does not have yet. Google Workspace and most other "
                             "providers work today."}
        if conn.execute("SELECT 1 FROM out_mailboxes WHERE email=?", (email_addr,)).fetchone():
            return {"error": "That inbox is already connected."}
        if not body.get("password"):                     # saving an address alone connects nothing, and looks like it did
            return {"error": "An app password is needed too, or nothing can be sent from this address. "
                             "The steps above make one; it takes about two minutes."}
        mid = store.add_mailbox(conn, email_addr, values)
    if body.get("password"):
        mailer.save_password(email_addr, body["password"].replace(" ", ""))
        mb = conn.execute("SELECT * FROM out_mailboxes WHERE id=?", (mid,)).fetchone()
        if mb["status"] == "broken":                     # a new password is the fix for a broken login
            store.update_mailbox(conn, mid, {"status": "active", "status_reason": ""})
    return {"id": mid}


def inbox_check(conn, body) -> dict:
    mb = conn.execute("SELECT * FROM out_mailboxes WHERE id=?", (int(body["id"]),)).fetchone()
    return health.check_inbox(conn, mb, mailer.load_password(mb["email"]), deep=bool(body.get("deep")))


def inbox_status(conn, body) -> dict:
    """Pause, resume or remove an inbox. Removing is refused while leads are mid-conversation with it."""
    mid, action = int(body["id"]), body.get("action")
    mb = conn.execute("SELECT * FROM out_mailboxes WHERE id=?", (mid,)).fetchone()
    if action == "pause":
        store.update_mailbox(conn, mid, {"status": "paused", "status_reason": "Paused by you."})
    elif action == "resume":
        store.update_mailbox(conn, mid, {"status": "active", "status_reason": "", "resume_at": None})
    elif action == "remove":
        if conn.execute("SELECT 1 FROM out_messages WHERE mailbox_id=? LIMIT 1", (mid,)).fetchone():
            return {"error": "This inbox has sent email, so its history is kept. Pause it instead."}
        conn.execute("DELETE FROM out_mailboxes WHERE id=?", (mid,))
        conn.commit()
        mailer.forget_password(mb["email"])
    return {"ok": True}


def test_send(conn, body) -> dict:
    """One real email through a real inbox, to an address of yours. Not recorded as a send."""
    boxes = [m for m in store.mailboxes(conn) if mailer.load_password(m["email"])]
    if not boxes:
        return {"error": "Connect the mailbox first."}
    mb = boxes[0]
    p = preview(conn, body)
    if p.get("error") or p["missing"]:
        return {"error": p.get("error") or "Empty merge fields: " + ", ".join(p["missing"])}
    text, _ = store.render(body.get("body") or "", p["values"])
    msg = mailer.build_message(mb, store.get_settings(conn), body["to"], "[TEST] " + (p["subject"] or "(follow-up, sent as a reply)"),
                               text, look=p["look"])
    try:
        mailer.SmtpTransport(mb, mailer.load_password(mb["email"])).send(msg)
    except (mailer.NotSent, mailer.Unsure) as e:
        return {"error": f"Send failed: {e}"}
    return {"ok": True, "as_if_to": p["to"], "from": mb["email"]}


def launch(conn, body) -> dict:
    """Launch, launch to a careful first few, or send a running campaign to the rest."""
    cid = int(body["id"])
    camp = store.load_campaign(conn, cid)
    s = _public_settings(conn)
    blocks = [o["text"] for o in store.preflight(conn, camp, store.get_settings(conn), s["has_password"]) if o["level"] == "block"]
    if camp["status"] == "done":
        blocks.append("This campaign has finished.")
    if blocks:
        return {"error": " ".join(blocks)}
    start = store.parse_iso(body["start_at"]) if body.get("start_at") else store.now_utc()
    return store.launch(conn, cid, max(start, store.now_utc()), first=int(body["first"]) if body.get("first") else None)


def set_status(conn, body) -> dict:
    status = body["status"]
    if status not in ("active", "paused"):
        return {"error": "Unknown status."}
    conn.execute("UPDATE out_campaigns SET status=? WHERE id=? AND status IN ('active','paused')", (status, int(body["id"])))
    conn.commit()
    return {"ok": True}


def duplicate(conn, body) -> dict:
    camp = store.load_campaign(conn, int(body["id"]))
    camp.pop("id")
    camp["name"] += " (copy)"
    camp["start_at"] = None
    return {"id": store.save_campaign(conn, camp)}


def delete(conn, body) -> dict:
    cid = int(body["id"])
    if conn.execute("SELECT COUNT(*) FROM out_enrollments WHERE campaign_id=?", (cid,)).fetchone()[0]:
        return {"error": "A campaign that has launched keeps its history. Pause it instead."}
    store.save_campaign(conn, {"id": cid, "steps": []})
    conn.execute("DELETE FROM out_campaigns WHERE id=?", (cid,))
    conn.commit()
    return {"ok": True}


def dnc(conn, _q) -> dict:
    return {"rows": [dict(r) for r in conn.execute("SELECT * FROM out_suppressed ORDER BY added_at DESC LIMIT 500")],
            "dead": store.dead_addresses()[:500]}


def revive(conn, body) -> dict:
    store.revive(body["email"])
    return {"ok": True}


def dnc_add(conn, body) -> dict:
    value = (body.get("value") or "").strip().lower()
    if not value:
        return {"error": "Type an address or a domain."}
    store.suppress(conn, "email" if "@" in value else "domain", value.lstrip("@"), body.get("reason") or "added by hand")
    return {"ok": True}


def dnc_remove(conn, body) -> dict:
    conn.execute("DELETE FROM out_suppressed WHERE kind=? AND value=?", (body["kind"], body["value"]))
    conn.commit()
    return {"ok": True}


def outcome(conn, body) -> dict:
    conn.execute("UPDATE out_enrollments SET outcome=? WHERE id=?", (body.get("outcome"), int(body["enrollment_id"])))
    conn.commit()
    return {"ok": True}


def resume_sending(conn, _body) -> dict:
    store.set_settings(conn, {"paused_reason": ""})
    return {"ok": True}


def set_schedule(conn, body) -> dict:
    s = _public_settings(conn)
    if body.get("on") and not s["has_password"]:
        return {"error": "Connect the mailbox first."}
    return {"message": mailer.schedule(bool(body.get("on")))}


def home(_q) -> dict:
    """The level above projects: one card each."""
    cards = []
    for path in store.list_projects():
        if not enter(path.name):
            continue
        conn = store.connect()
        try:
            one = lambda q: conn.execute(q).fetchone()[0]
            jobs = runs.list_runs(conn)
            cards.append({
                "slug": path.name, "name": store.CONF["name"], "country": store.CONF["country"], "folder": str(path),
                "leads": one("SELECT COUNT(*) FROM businesses"),
                "inboxes": one("SELECT COUNT(*) FROM out_contacts WHERE check_status='ok'"),
                "campaigns_live": one("SELECT COUNT(*) FROM out_campaigns WHERE status='active'"),
                "replies_waiting": one("SELECT COUNT(*) FROM out_enrollments WHERE status='replied' AND outcome IS NULL"),
                "last_scrape": one("SELECT MAX(last_seen) FROM businesses"),
                "running": [j["label"] for j in jobs if j["state"] == "running"],
                "mailbox": ", ".join(m["email"] for m in store.mailboxes(conn))})
        finally:
            conn.close()
    return {"projects": cards, "root": str(store.projects_root()), "countries": sorted(COUNTRY_TZ),
            "has_ai_key": bool(ask.load_key())}


# Enough to start a project with the right clock; any IANA timezone can be typed instead.
COUNTRY_TZ = {"AU": "Australia/Sydney", "NZ": "Pacific/Auckland", "IN": "Asia/Kolkata", "GB": "Europe/London",
              "IE": "Europe/Dublin", "US": "America/New_York", "CA": "America/Toronto", "SG": "Asia/Singapore",
              "AE": "Asia/Dubai", "ZA": "Africa/Johannesburg", "DE": "Europe/Berlin", "FR": "Europe/Paris"}


def new_project(body) -> dict:
    name = (body.get("name") or "").strip()
    country = (body.get("country") or "").strip().upper()
    if not name or len(country) != 2:
        return {"error": "Give the project a name and a two-letter country code, like AU."}
    folder = store.projects_root() / (runs.slug(name).replace("_", "-") or "project")
    if folder.exists():
        return {"error": f"There is already a folder called {folder.name}."}
    projects.create(str(folder), name, country, body.get("tz") or COUNTRY_TZ.get(country, "UTC"))
    return {"slug": folder.name}


def ask_route(conn, body) -> dict:
    text = (body.get("text") or "").strip()
    if not text:
        return {"error": "Type what you need."}
    try:
        return ask.ask(conn, str(body.get("conversation_id") or "default"), text)
    except Exception as e:
        kind = type(e).__name__
        if kind in ("AuthenticationError", "PermissionDeniedError") or "api_key" in str(e) or "auth" in str(e).lower():
            return {"error": "The assistant needs an Anthropic API key. Add one on the Projects screen. Everything else works without it."}
        if kind == "RateLimitError":
            return {"error": "The AI service is rate limiting this key. Wait a minute and ask again."}
        if kind == "APIConnectionError":
            return {"error": "Could not reach the AI service. Check the internet connection."}
        return {"error": f"The assistant hit a problem: {kind}: {e}"}


def jobs(conn, _q) -> dict:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(businesses)")}
    with_email = conn.execute("SELECT COUNT(*) FROM businesses WHERE COALESCE(email,'') <> ''").fetchone()[0] if "email" in cols else 0
    return {"runs": runs.list_runs(conn), "enrich_todo": runs.enrich_todo(conn), "country": store.CONF["country"],
            "leads": conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0], "with_email": with_email}


def scrape_start(conn, body) -> dict:
    checked = runs.plan(body)            # never trust a plan the page sends back; work it out again
    return checked if checked.get("error") else runs.start_scrape(conn, checked["request"])


GET = {"/api/jobs": jobs, "/api/inbox": inbox, "/api/state": state, "/api/campaign": campaign, "/api/dnc": dnc}
POST = {"/api/ask": ask_route, "/api/scrape/plan": lambda c, b: runs.plan(b), "/api/scrape/start": scrape_start,
        "/api/scrape/resume": lambda c, b: runs.start_scrape(c, {}, resume_id=int(b["id"])),
        "/api/run/stop": lambda c, b: runs.stop(c, int(b["id"])), "/api/enrich/start": lambda c, b: runs.start_enrich(c),
        "/api/board/annotation": save_annotation, "/api/campaign/from-leads": campaign_from_leads,
        "/api/audience": audience, "/api/preview": preview, "/api/settings": save_settings,
        "/api/inbox/save": inbox_save, "/api/inbox/check": inbox_check, "/api/inbox/status": inbox_status, "/api/test-send": test_send,
        "/api/campaign/save": lambda c, b: {"id": store.save_campaign(c, b)}, "/api/campaign/launch": launch,
        "/api/campaign/status": set_status, "/api/campaign/duplicate": duplicate, "/api/campaign/delete": delete,
        "/api/dead/revive": revive, "/api/dnc/add": dnc_add, "/api/dnc/remove": dnc_remove, "/api/outcome": outcome,
        "/api/resume-sending": resume_sending, "/api/schedule": set_schedule, "/api/tick": lambda c, b: mailer.tick(c)}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _run(self, fn, arg) -> None:
        conn = store.connect()
        try:
            self._send(200, json.dumps(fn(conn, arg)).encode(), "application/json")
        except Exception as e:
            self._send(500, json.dumps({"error": f"{type(e).__name__}: {e}"}).encode(), "application/json")
        finally:
            conn.close()

    def _route(self):
        """('home', rest) or ('project', rest) with the project entered, or None after a 404."""
        path = urlparse(self.path).path
        if not path.startswith("/p/"):
            return "home", path
        slug, _, rest = path[3:].partition("/")
        if not enter(slug):
            self._send(404, b"No such project.", "text/plain")
            return None
        return "project", "/" + rest

    def do_GET(self):
        routed = self._route()
        if not routed:
            return
        where, path = routed
        query = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        if where == "home":
            if path == "/":
                return self._send(200, HOME.read_bytes(), "text/html; charset=utf-8")
            if path == "/api/home":
                return self._send(200, json.dumps(home(query)).encode(), "application/json")
        elif path == "/":
            return self._send(200, PANEL.read_bytes(), "text/html; charset=utf-8")
        elif path == "/leads":
            try:
                return self._send(200, board_page(), "text/html; charset=utf-8")
            except SystemExit as e:        # the board builder reports a bad spec this way
                return self._send(500, f"The leads board could not be built: {e}".encode(), "text/plain; charset=utf-8")
        elif path in GET:
            return self._run(GET[path], query)
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        if (origin and origin != f"http://{host}") or "json" not in self.headers.get("Content-Type", ""):
            return self._send(403, b"forbidden", "text/plain")    # another website cannot drive the mailbox
        routed = self._route()
        if not routed:
            return
        where, path = routed
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if where == "home" and path == "/api/projects/new":
            return self._send(200, json.dumps(new_project(body)).encode(), "application/json")
        if where == "home" and path == "/api/ai-key":
            ask.save_key(body.get("key") or "")
            return self._send(200, b'{"ok": true}', "application/json")
        if where == "project" and path in POST:
            return self._run(POST[path], body)
        self._send(404, b"not found", "text/plain")

    def log_message(self, *_):
        pass


def serve(port: int, open_project: Path | None = None) -> None:
    if open_project:
        store.remember_project(open_project)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"maps-leads: http://127.0.0.1:{port}" + (f"/p/{open_project.name}/leads" if open_project else ""))
    httpd.serve_forever()
