"""store.py: the outreach tables inside leads.db, plus everything that reads or
writes them. Scraped rows (businesses, pulls_log, business_profiles) are only
ever read here.

One contact = one email address, not one Google Maps listing: a franchise that
lists the same inbox on 299 listings gets one email, not 299.
"""
from __future__ import annotations

import json
import math
import os
import random
import re
import sqlite3
import sys
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO), str(REPO / "leads")]
import geo  # noqa: E402
import project as projects  # noqa: E402

# Which project the current piece of work is on. The app serves several projects at once, one
# request per thread, so this is per thread: a request for one client can never read another's.
_ctx = threading.local()


def use(project_dir: Path) -> None:
    _ctx.project, _ctx.conf = Path(project_dir), projects.settings(Path(project_dir))


def __getattr__(name: str):            # store.PROJECT and store.CONF, as the other modules read them
    if name == "PROJECT":
        return getattr(_ctx, "project", None)
    if name == "CONF":
        return getattr(_ctx, "conf", dict(projects.DEFAULTS))
    raise AttributeError(name)


SCHEMA = """
CREATE TABLE IF NOT EXISTS out_contacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    email        TEXT UNIQUE,
    domain       TEXT,
    place_id     TEXT,              -- the listing used for merge fields (most reviewed)
    places       INTEGER,           -- how many listings share this address
    trade        TEXT,
    state        TEXT,
    tz           TEXT,
    is_role      INTEGER DEFAULT 0,
    check_status TEXT,              -- ok | bad_syntax | placeholder | gov_edu | bounced
    mx_status    TEXT,              -- NULL (not checked yet) | ok | none
    mx_checked_at TEXT
);
CREATE TABLE IF NOT EXISTS out_suppressed (
    kind     TEXT CHECK (kind IN ('email','domain')),
    value    TEXT,
    reason   TEXT,
    added_at TEXT,
    PRIMARY KEY (kind, value)
);
CREATE TABLE IF NOT EXISTS out_campaigns (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT,
    status        TEXT DEFAULT 'draft',   -- draft | active | paused | done
    audience_json TEXT DEFAULT '{}',
    window_start  TEXT DEFAULT '09:00',
    window_end    TEXT DEFAULT '16:30',
    weekdays      TEXT DEFAULT '1,2,3,4,5',  -- ISO weekday numbers, recipient's local time
    start_at      TEXT,
    created_at    TEXT,
    launched_at   TEXT
);
CREATE TABLE IF NOT EXISTS out_steps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    position    INTEGER,
    gap_days    INTEGER DEFAULT 0        -- days after the previous email
);
CREATE TABLE IF NOT EXISTS out_variants (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id  INTEGER,
    arm      INTEGER,                    -- 0 = A, 1 = B ...
    subject  TEXT,                       -- blank on a follow-up = reply in the same thread
    body     TEXT
);
CREATE TABLE IF NOT EXISTS out_enrollments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id   INTEGER,
    contact_id    INTEGER,
    arm           INTEGER,
    status        TEXT DEFAULT 'active',  -- active | replied | bounced | unsubscribed | finished | stopped
    next_step     INTEGER DEFAULT 1,
    next_due      TEXT,
    first_subject TEXT,
    refs          TEXT DEFAULT '',        -- space-separated Message-IDs sent so far
    outcome       TEXT,                   -- set by hand on a reply: positive | negative
    enrolled_at   TEXT,
    UNIQUE (campaign_id, contact_id)
);
CREATE TABLE IF NOT EXISTS out_messages (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER,
    step_position INTEGER,
    variant_id    INTEGER,
    message_id    TEXT UNIQUE,
    to_email      TEXT,
    subject       TEXT,
    sent_at       TEXT
);
CREATE TABLE IF NOT EXISTS out_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    enrollment_id INTEGER,
    kind          TEXT,   -- sent | reply | auto_reply | bounce_hard | bounce_soft | unsubscribe | stopped | auto_pause
    step_position INTEGER,
    at            TEXT,
    detail        TEXT,
    ref           TEXT UNIQUE             -- inbound Message-ID, so a re-read mailbox never double counts
);
CREATE TABLE IF NOT EXISTS out_settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS out_mailboxes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT UNIQUE,
    from_name     TEXT DEFAULT '',
    provider      TEXT DEFAULT 'google',     -- google | other   (microsoft needs a sign-in flow we have not built)
    smtp_host     TEXT, smtp_port INTEGER, imap_host TEXT, imap_port INTEGER DEFAULT 993,
    signature     TEXT DEFAULT '',           -- this sender's sign-off: name, role, phone
    daily_cap     INTEGER DEFAULT 40, ramp_start INTEGER DEFAULT 10, ramp_step INTEGER DEFAULT 3,
    gap_min       REAL DEFAULT 3, gap_max REAL DEFAULT 9,
    status        TEXT DEFAULT 'active',     -- active | paused (by you) | resting (until resume_at) | broken (needs you)
    status_reason TEXT DEFAULT '',
    resume_at     TEXT,                      -- resting ends
    slow_until    TEXT,                      -- half speed until
    next_send_after TEXT,
    imap_cursor   TEXT DEFAULT '{}',
    last_watch    TEXT,
    health        TEXT DEFAULT '{}',
    health_at     TEXT,
    created_at    TEXT
);
CREATE TABLE IF NOT EXISTS out_picked (          -- leads hand-picked on the board for one campaign
    campaign_id INTEGER,
    contact_id  INTEGER,
    PRIMARY KEY (campaign_id, contact_id)
);
CREATE TABLE IF NOT EXISTS board_annotations (   -- stages, notes and follow-ups set on the leads board
    place_id   TEXT PRIMARY KEY,
    json       TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_out_enr_due ON out_enrollments(status, next_due);
CREATE INDEX IF NOT EXISTS idx_out_msg_enr ON out_messages(enrollment_id);
CREATE INDEX IF NOT EXISTS idx_out_msg_to ON out_messages(to_email);
CREATE INDEX IF NOT EXISTS idx_out_evt_enr ON out_events(enrollment_id);
"""

# The 2026-09-15 roadmap tables. One template per campaign, no versions, no
# steps: they cannot hold a cadence, and they were never used.
LEGACY_TABLES = ["campaign_leads", "campaigns", "templates", "segments"]

DEFAULTS = {
    "from_name": "", "from_email": "",
    "smtp_host": "smtp.gmail.com", "smtp_port": 465, "imap_host": "imap.gmail.com",
    "daily_cap": 40, "ramp_start": 10, "ramp_step": 3,   # a new mailbox earns its volume
    "gap_min": 3, "gap_max": 9,                          # minutes between two sends
    "footer": "",
    "unsub_line": "If you'd rather not hear from me, reply \"unsubscribe\" and I won't email again.",
    "bounce_pause_pct": 4,
    "paused_reason": "",
}

EMAIL_RE = re.compile(r"^[a-z0-9][a-z0-9._%+\-]*@(?:[a-z0-9\-]+\.)+[a-z]{2,}$")
ROLE_LOCALS = {"info", "admin", "sales", "enquiries", "enquiry", "office", "hello", "contact", "mail",
               "accounts", "reception", "support", "team", "bookings", "service", "quotes"}
FREEMAIL = {"gmail.com", "outlook.com", "hotmail.com", "bigpond.com", "yahoo.com", "outlook.com.au",
            "yahoo.com.au", "live.com.au", "live.com", "icloud.com", "optusnet.com.au", "me.com",
            "bigpond.net.au", "iinet.net.au", "tpg.com.au", "westnet.com.au", "internode.on.net"}
NAME_NOISE = re.compile(r"\b(pty\.?\s*ltd\.?|p/l|ltd\.?|limited)\b", re.I)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path or _ctx.project / "leads.db"), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# Columns added after a table first shipped. CREATE TABLE IF NOT EXISTS never adds these to an existing project.
ADDED_COLUMNS = {
    "out_enrollments": {"mailbox_id": "INTEGER", "soft_strikes": "INTEGER DEFAULT 0"},
    "out_messages": {"mailbox_id": "INTEGER", "state": "TEXT DEFAULT 'sent'"},      # sending | sent
    "out_steps": {"same_thread": "INTEGER DEFAULT 1"},
    "out_variants": {"paused": "INTEGER DEFAULT 0"},
    "out_campaigns": {"look": "TEXT DEFAULT 'plain'", "first_plain": "INTEGER DEFAULT 1"},
}


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Create the outreach tables. Drops a legacy roadmap table only when it is empty."""
    dropped = []
    for t in LEGACY_TABLES:
        exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)).fetchone()
        if exists and conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == 0:
            conn.execute(f"DROP TABLE {t}")
            dropped.append(t)
    from pipeline import SCHEMA as LEADS_SCHEMA      # leads/ is on the path
    conn.executescript(LEADS_SCHEMA)
    conn.executescript(SCHEMA)
    for table, cols in ADDED_COLUMNS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, decl in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    conn.commit()
    return dropped


# ── settings ────────────────────────────────────────────────────────────────

def get_settings(conn) -> dict:
    out = dict(DEFAULTS)
    for r in conn.execute("SELECT key, value FROM out_settings"):
        out[r["key"]] = json.loads(r["value"])
    return out


def set_settings(conn, values: dict) -> None:
    for k, v in values.items():
        conn.execute("INSERT INTO out_settings(key, value) VALUES(?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, json.dumps(v)))
    conn.commit()


# ── inboxes ─────────────────────────────────────────────────────────────────

MAILBOX_FIELDS = ("from_name", "provider", "smtp_host", "smtp_port", "imap_host", "imap_port", "signature",
                  "daily_cap", "ramp_start", "ramp_step", "gap_min", "gap_max")
PROVIDERS = {"google": {"smtp_host": "smtp.gmail.com", "smtp_port": 465, "imap_host": "imap.gmail.com", "imap_port": 993},
             "other": {"smtp_host": "", "smtp_port": 465, "imap_host": "", "imap_port": 993}}


def mailboxes(conn) -> list[sqlite3.Row]:
    """Every inbox in this project. A project set up before there were several inboxes carries its one
    mailbox in the settings; it becomes the first row here, pace and all, the first time anyone looks."""
    rows = conn.execute("SELECT * FROM out_mailboxes ORDER BY id").fetchall()
    if not rows:
        old = get_settings(conn)
        if old.get("from_email"):
            add_mailbox(conn, old["from_email"], {k: old[k] for k in MAILBOX_FIELDS if k in old})
            conn.execute("UPDATE out_mailboxes SET next_send_after=?, imap_cursor=?", (
                old.get("next_send_after"), json.dumps(old.get("imap_cursor") or {})))
            conn.execute("UPDATE out_enrollments SET mailbox_id=(SELECT id FROM out_mailboxes) WHERE mailbox_id IS NULL "
                         "AND EXISTS (SELECT 1 FROM out_messages m WHERE m.enrollment_id=out_enrollments.id)")
            conn.execute("UPDATE out_messages SET mailbox_id=(SELECT id FROM out_mailboxes) WHERE mailbox_id IS NULL")
            conn.commit()
            rows = conn.execute("SELECT * FROM out_mailboxes ORDER BY id").fetchall()
    return rows


def add_mailbox(conn, email: str, values: dict) -> int:
    email = email.strip().lower()
    base = {**{k: DEFAULTS[k] for k in ("daily_cap", "ramp_start", "ramp_step", "gap_min", "gap_max")},
            **PROVIDERS.get(values.get("provider") or "google", PROVIDERS["google"]), "provider": "google", "from_name": "", "signature": ""}
    row = {**base, **{k: v for k, v in values.items() if k in MAILBOX_FIELDS and v not in (None, "")}}
    cur = conn.execute(f"INSERT INTO out_mailboxes(email, created_at, {', '.join(row)}) VALUES(?, ?, {', '.join('?' * len(row))})",
                       (email, iso(now_utc()), *row.values()))
    conn.commit()
    return cur.lastrowid


def update_mailbox(conn, mailbox_id: int, values: dict) -> None:
    allowed = MAILBOX_FIELDS + ("status", "status_reason", "resume_at", "slow_until", "next_send_after", "imap_cursor",
                                "last_watch", "health", "health_at")
    sets = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in values.items() if k in allowed}
    if sets:
        conn.execute(f"UPDATE out_mailboxes SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), mailbox_id))
        conn.commit()


def mailbox_capacity(conn, mb, now: datetime) -> dict:
    """How many more emails this inbox may send today. A new inbox earns its volume a little each day;
    an inbox the provider has warned runs at half speed for a while."""
    first = conn.execute("SELECT MIN(sent_at) FROM out_messages WHERE mailbox_id=? AND state='sent'", (mb["id"],)).fetchone()[0]
    days = (now - parse_iso(first)).days if first else 0
    cap = int(min(mb["daily_cap"], mb["ramp_start"] + mb["ramp_step"] * days))
    if mb["slow_until"] and now < parse_iso(mb["slow_until"]):
        cap = max(1, cap // 2)
    sent = conn.execute("SELECT COUNT(*) FROM out_messages WHERE mailbox_id=? AND sent_at > ?",
                        (mb["id"], iso(now - timedelta(hours=24)))).fetchone()[0]
    return {"cap": cap, "sent_24h": sent, "left": max(0, cap - sent)}


def total_pace(conn) -> dict:
    """The project's combined pace, for the forecast: every inbox that can send, added together."""
    live = [m for m in mailboxes(conn) if m["status"] in ("active", "resting")]
    if not live:
        return {k: DEFAULTS[k] for k in ("daily_cap", "ramp_start", "ramp_step")}
    return {k: sum(m[k] for m in live) for k in ("daily_cap", "ramp_start", "ramp_step")}


def after_sending_days(start: datetime, days: int, weekdays: str) -> datetime:
    """`days` sending days after `start`. A gap of 3 from a Friday, Monday to Friday, lands on Wednesday:
    nobody means "three days, two of them a weekend" when they say follow up in three days."""
    allowed = {int(d) for d in (weekdays or "1,2,3,4,5").split(",") if d} or {1, 2, 3, 4, 5}
    at = start
    while days > 0:
        at += timedelta(days=1)
        if at.isoweekday() in allowed:
            days -= 1
    return at


# ── contacts ────────────────────────────────────────────────────────────────

def _host(url: str | None) -> str:
    if not url:
        return ""
    h = urlparse(url if "//" in url else "//" + url).hostname or ""
    return h[4:] if h.startswith("www.") else h


def _junk_domains() -> set[str]:
    try:
        spec = _ctx.project / "dashboard.spec.json"
        found = _find_key(json.loads(spec.read_text()), "junk_email_domains") or []
    except (OSError, ValueError, TypeError):      # no board spec in this project yet
        found = []
    return {d.lower() for d in found}


def _find_key(node, key):
    if isinstance(node, dict):
        if key in node:
            return node[key]
        node = list(node.values())
    if isinstance(node, list):
        for v in node:
            hit = _find_key(v, key)
            if hit is not None:
                return hit
    return None


def sync_contacts(conn) -> dict:
    """Rebuild out_contacts from businesses.email. Safe to re-run after new enrichment:
    existing contacts keep their id, their delivery checks and their bounce status."""
    if "email" not in {r[1] for r in conn.execute("PRAGMA table_info(businesses)")}:
        return {}                                    # nothing has been enriched in this project yet
    junk = _junk_domains()
    groups: dict[str, list] = defaultdict(list)
    for r in conn.execute("SELECT place_id, email, website, review_count, signal_score, profile, state, lat, lng "
                          "FROM businesses WHERE COALESCE(email,'') <> ''"):
        groups[unquote(r["email"]).strip().lower()].append(r)     # the crawl left "%20info@..." on ~100 rows

    counts = Counter()
    for email, rows in groups.items():
        domain = email.rsplit("@", 1)[-1]
        best = max(rows, key=lambda r: (r["review_count"] or 0, r["signal_score"] or 0))
        hosts = {_host(r["website"]) for r in rows} - {""}
        if not EMAIL_RE.match(email):
            status = "bad_syntax"
        elif domain in junk or any(domain.endswith("." + j) for j in junk):
            status = "placeholder"
        elif len(rows) >= 3 and len(hosts) >= 3 and not any(h == domain or h.endswith("." + domain) for h in hosts):
            # the same inbox on three unrelated websites is a theme author or a
            # site-builder default, never the owner of all three businesses
            status = "placeholder"
        elif domain.endswith((".gov.au", ".edu.au")):
            status = "gov_edu"
        else:
            status = "ok"
        state = best["state"]
        state = state or geo.state_from_coords(_ctx.conf["country"], best["lat"], best["lng"])
        counts[status] += 1
        conn.execute(
            "INSERT INTO out_contacts(email, domain, place_id, places, trade, state, tz, is_role, check_status) "
            "VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(email) DO UPDATE SET place_id=excluded.place_id, "
            "places=excluded.places, trade=excluded.trade, state=excluded.state, tz=excluded.tz, "
            "check_status=CASE WHEN out_contacts.check_status='bounced' THEN 'bounced' ELSE excluded.check_status END",
            (email, domain, best["place_id"], len(rows), best["profile"], state, geo.tz_for(_ctx.conf["country"], state, _ctx.conf["default_tz"]),
             int(email.split("@")[0] in ROLE_LOCALS), status))
    # an address that has left the scraped data (re-crawled, corrected) goes too, unless it has history
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _live(email TEXT PRIMARY KEY)")
    conn.execute("DELETE FROM _live")
    conn.executemany("INSERT INTO _live VALUES(?)", [(e,) for e in groups])
    conn.execute("DELETE FROM out_contacts WHERE email NOT IN (SELECT email FROM _live) "
                 "AND id NOT IN (SELECT contact_id FROM out_enrollments)")
    conn.commit()
    return dict(counts)


def check_mx(conn, contact_ids: list[int]) -> dict:
    """Does the domain accept mail at all? Free, and it removes the dead domains
    that would otherwise become hard bounces. Freemail domains are skipped."""
    import dns.exception
    import dns.resolver
    from concurrent.futures import ThreadPoolExecutor

    rows = conn.execute(f"SELECT id, domain FROM out_contacts WHERE mx_status IS NULL AND id IN "
                        f"({','.join('?' * len(contact_ids))})", contact_ids).fetchall() if contact_ids else []
    domains = {r["domain"] for r in rows}
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 6

    def probe(domain: str):
        if domain in FREEMAIL:
            return domain, "ok"
        for rtype in ("MX", "A"):
            try:
                resolver.resolve(domain, rtype)
                return domain, "ok"
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                continue
            except dns.exception.DNSException:
                return domain, None      # resolver trouble is not evidence; check again next time
        return domain, "none"

    with ThreadPoolExecutor(16) as pool:
        verdict = dict(pool.map(probe, domains))
    stamp = iso(now_utc())
    for r in rows:
        if verdict[r["domain"]]:
            conn.execute("UPDATE out_contacts SET mx_status=?, mx_checked_at=? WHERE id=?",
                         (verdict[r["domain"]], stamp, r["id"]))
    conn.commit()
    return dict(Counter(v or "unknown" for v in verdict.values()))


# ── dead addresses: the one thing every project shares ──────────────────────
# Do-not-contact is a preference and belongs to a project (really, to its mailbox). A hard
# bounce is different: it is a fact about the address, true for every project, and every
# repeat bounce costs the sending mailbox reputation. So dead addresses live outside any
# project, with no note of which project found them.

def shared_dir() -> Path:
    if os.environ.get("MAPS_LEADS_HOME"):
        return Path(os.environ["MAPS_LEADS_HOME"])
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/maps-leads"
    return Path(os.environ.get("APPDATA") or Path.home() / ".local/share") / "maps-leads"


def _shared() -> sqlite3.Connection:
    shared_dir().mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(shared_dir() / "shared.db"), timeout=30)
    conn.execute("CREATE TABLE IF NOT EXISTS dead_addresses (email TEXT PRIMARY KEY, why TEXT, added_at TEXT)")
    return conn


def projects_root() -> Path:
    return Path(os.environ.get("MAPS_LEADS_PROJECTS") or Path.home() / "maps-leads-projects")


def list_projects() -> list[Path]:
    """Every folder under the projects root that has a project.json, plus any project opened from
    somewhere else (remembered in the shared database)."""
    root = projects_root()
    found = {p.parent.resolve() for p in root.glob("*/project.json")} if root.exists() else set()
    with _shared() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS known_projects (path TEXT PRIMARY KEY)")
        found |= {Path(r[0]) for r in conn.execute("SELECT path FROM known_projects") if (Path(r[0]) / "project.json").exists()}
    return sorted(found, key=lambda p: p.name)


def remember_project(path: Path) -> None:
    if path.resolve().parent != projects_root().resolve():
        with _shared() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS known_projects (path TEXT PRIMARY KEY)")
            conn.execute("INSERT OR IGNORE INTO known_projects VALUES(?)", (str(path.resolve()),))


def mark_dead(email: str, why: str = "") -> None:
    with _shared() as conn:
        conn.execute("INSERT OR IGNORE INTO dead_addresses VALUES(?,?,?)", (email.lower(), why[:200], iso(now_utc())))


def revive(email: str) -> None:
    with _shared() as conn:
        conn.execute("DELETE FROM dead_addresses WHERE email=?", (email.lower(),))


def dead_addresses() -> list[dict]:
    with _shared() as conn:
        return [{"email": e, "why": w, "added_at": a} for e, w, a in
                conn.execute("SELECT email, why, added_at FROM dead_addresses ORDER BY added_at DESC")]


def is_dead(email: str) -> bool:
    with _shared() as conn:
        return bool(conn.execute("SELECT 1 FROM dead_addresses WHERE email=?", (email.lower(),)).fetchone())


# ── do not contact ──────────────────────────────────────────────────────────

def suppress(conn, kind: str, value: str, reason: str) -> None:
    conn.execute("INSERT OR IGNORE INTO out_suppressed(kind, value, reason, added_at) VALUES(?,?,?,?)",
                 (kind, value.strip().lower(), reason, iso(now_utc())))
    conn.commit()


def is_suppressed(conn, email: str, place_id: str | None = None) -> bool:
    domain = email.rsplit("@", 1)[-1]
    if conn.execute("SELECT 1 FROM out_suppressed WHERE (kind='email' AND value=?) OR (kind='domain' AND value=?)",
                    (email, domain)).fetchone():
        return True
    return bool(place_id and conn.execute("SELECT 1 FROM suppressed WHERE place_id=?", (place_id,)).fetchone())


# ── audience ────────────────────────────────────────────────────────────────

def audience(conn, f: dict, campaign_id: int | None = None) -> dict:
    """Who a campaign would reach, with every exclusion counted and named."""
    where, args = ["1=1"], []
    if f.get("trades"):
        where.append(f"c.trade IN ({','.join('?' * len(f['trades']))})")
        args += f["trades"]
    if f.get("states"):
        where.append(f"c.state IN ({','.join('?' * len(f['states']))})")
        args += f["states"]
    for key, col in (("min_rating", "b.rating"), ("min_reviews", "b.review_count"), ("min_score", "b.signal_score")):
        if f.get(key) not in (None, ""):
            where.append(f"COALESCE({col},0) >= ?")
            args.append(float(f[key]))
    if f.get("picked"):
        where.append("c.id IN (SELECT contact_id FROM out_picked WHERE campaign_id = ?)")
        args.append(campaign_id)
    if f.get("website") in ("yes", "no"):
        where.append("COALESCE(b.has_website,0) = ?")
        args.append(1 if f["website"] == "yes" else 0)

    rows = conn.execute(
        f"SELECT c.id, c.email, c.domain, c.place_id, c.places, c.trade, c.state, c.check_status, c.mx_status, "
        f"  EXISTS(SELECT 1 FROM out_suppressed s WHERE (s.kind='email' AND s.value=c.email) "
        f"         OR (s.kind='domain' AND s.value=c.domain)) "
        f"  OR EXISTS(SELECT 1 FROM suppressed p WHERE p.place_id=c.place_id) AS dnc, "
        f"  EXISTS(SELECT 1 FROM out_enrollments e WHERE e.contact_id=c.id AND e.campaign_id IS NOT ?) AS contacted "
        f"FROM out_contacts c JOIN businesses b ON b.place_id=c.place_id WHERE {' AND '.join(where)}",
        [campaign_id] + args).fetchall()

    excluded, keep = Counter(), []
    dead = {d["email"] for d in dead_addresses()}
    for r in rows:
        if r["email"] in dead:
            excluded["Address is dead (it bounced before, here or in another project)"] += 1
        elif r["check_status"] != "ok":
            excluded["Address looks wrong or is a website-builder placeholder"] += 1
        elif r["mx_status"] == "none":
            excluded["Domain does not accept mail"] += 1
        elif r["dnc"]:
            excluded["On the do-not-contact list"] += 1
        elif r["contacted"] and not f.get("allow_recontact"):
            excluded["Already in another campaign"] += 1
        elif r["places"] > 3 and not f.get("include_shared"):
            excluded["One inbox shared by more than 3 listings (chains)"] += 1
        else:
            keep.append(r)
    matched = len(keep)
    limit = int(f.get("max_leads") or 0)
    if limit and matched > limit:
        keep = random.Random(f.get("seed", 1)).sample(keep, limit)
    return {"matched": matched, "count": len(keep), "excluded": dict(excluded), "rows": keep}


# ── merge fields ────────────────────────────────────────────────────────────

TRADE_LABELS = {"HVAC/air-con install & service": "air conditioning",
                "Boutique renovation/building contractors": "renovation and building",
                "Electricians (residential/small commercial)": "electrical"}
FIELD_RE = re.compile(r"\{([a-z_]+)(?:\|([^}]*))?\}")
FIELDS = ["name", "short_name", "suburb", "state", "trade", "rating", "reviews", "website"]


def short_name(name: str) -> str:
    """'Auto King Mobile Mechanics | Eight Mile Plains' -> 'Auto King Mobile Mechanics'."""
    head = re.split(r"\s[|\-–—:]\s|\s*\|\s*", name or "")[0]
    return NAME_NOISE.sub("", head).strip(" ,.-")


def merge_values(conn, contact_id: int) -> dict:
    r = conn.execute("SELECT b.name, b.suburb, b.rating, b.review_count, b.website, c.state, c.trade "
                     "FROM out_contacts c JOIN businesses b ON b.place_id=c.place_id WHERE c.id=?",
                     (contact_id,)).fetchone()
    trade = r["trade"] or ""
    return {"name": r["name"] or "", "short_name": short_name(r["name"] or ""), "suburb": r["suburb"] or "",
            "state": r["state"] or "", "website": _host(r["website"]),
            "trade": TRADE_LABELS.get(trade, re.split(r"[/(]", trade)[0].strip().lower()),
            "rating": f"{r['rating']:g}" if r["rating"] else "", "reviews": str(r["review_count"] or "")}


def render(text: str, values: dict) -> tuple[str, list[str]]:
    """Fill {field} and {field|fallback}. Returns the text and the fields that came up
    empty with no fallback: those must never reach a real inbox as 'Hi ,'."""
    missing = []

    def sub(m):
        key, fallback = m.group(1), m.group(2)
        if key not in FIELDS:
            missing.append(key + " (not a field)")
            return m.group(0)
        val = values.get(key) or fallback
        if not val:
            missing.append(key)
        return val or ""

    return FIELD_RE.sub(sub, text or ""), missing


# ── campaigns ───────────────────────────────────────────────────────────────

def load_campaign(conn, cid: int) -> dict | None:
    c = conn.execute("SELECT * FROM out_campaigns WHERE id=?", (cid,)).fetchone()
    if not c:
        return None
    out = dict(c)
    out["audience"] = json.loads(out.pop("audience_json") or "{}")
    out["steps"] = []
    for s in conn.execute("SELECT * FROM out_steps WHERE campaign_id=? ORDER BY position", (cid,)):
        versions = [dict(v) for v in conn.execute("SELECT arm, subject, body, id, paused FROM out_variants "
                                                  "WHERE step_id=? ORDER BY arm", (s["id"],))]
        sent = conn.execute("SELECT COUNT(*) FROM out_messages m JOIN out_enrollments e ON e.id=m.enrollment_id "
                            "WHERE e.campaign_id=? AND m.step_position=?", (cid, s["position"])).fetchone()[0]
        out["steps"].append({"position": s["position"], "gap_days": s["gap_days"], "same_thread": s["same_thread"],
                             "versions": versions, "sent": sent})
    return out


def save_campaign(conn, doc: dict) -> int:
    """Create or update. Once a campaign has launched, an email that has already gone to someone is
    locked: changing it mid-test would make its numbers meaningless. An email nobody has received yet
    can still be edited, and a version can be rested or brought back at any time."""
    cid = doc.get("id")
    head = (doc.get("name") or "Untitled campaign", json.dumps(doc.get("audience") or {}),
            doc.get("window_start") or "09:00", doc.get("window_end") or "16:30",
            doc.get("weekdays") or "1,2,3,4,5", doc.get("start_at"), doc.get("look") or "plain",
            int(doc.get("first_plain", 1) if doc.get("first_plain") is not None else 1))
    launched = False
    if cid:
        launched = conn.execute("SELECT status FROM out_campaigns WHERE id=?", (cid,)).fetchone()["status"] != "draft"
        if launched:
            conn.execute("UPDATE out_campaigns SET name=?, window_start=?, window_end=?, weekdays=?, look=?, first_plain=? WHERE id=?",
                         (head[0], head[2], head[3], head[4], head[6], head[7], cid))
        else:
            conn.execute("UPDATE out_campaigns SET name=?, audience_json=?, window_start=?, window_end=?, weekdays=?, "
                         "start_at=?, look=?, first_plain=? WHERE id=?", head + (cid,))
    else:
        cid = conn.execute("INSERT INTO out_campaigns(name, audience_json, window_start, window_end, weekdays, "
                           "start_at, look, first_plain, created_at) VALUES(?,?,?,?,?,?,?,?,?)", head + (iso(now_utc()),)).lastrowid
    if launched:
        for pos, step in enumerate(doc.get("steps") or [], start=1):
            row = conn.execute("SELECT id FROM out_steps WHERE campaign_id=? AND position=?", (cid, pos)).fetchone()
            if not row:
                continue
            untouched = not conn.execute("SELECT 1 FROM out_messages m JOIN out_enrollments e ON e.id=m.enrollment_id "
                                         "WHERE e.campaign_id=? AND m.step_position=? LIMIT 1", (cid, pos)).fetchone()
            for arm, v in enumerate(step.get("versions") or []):
                conn.execute("UPDATE out_variants SET paused=? WHERE step_id=? AND arm=?", (int(bool(v.get("paused"))), row["id"], arm))
                if untouched:
                    conn.execute("UPDATE out_variants SET subject=?, body=? WHERE step_id=? AND arm=?",
                                 ((v.get("subject") or "").strip(), v.get("body") or "", row["id"], arm))
            if untouched and pos > 1:
                conn.execute("UPDATE out_steps SET gap_days=?, same_thread=? WHERE id=?",
                             (max(1, int(step.get("gap_days") or 3)), int(step.get("same_thread", 1)), row["id"]))
            if not conn.execute("SELECT 1 FROM out_variants WHERE step_id=? AND paused=0", (row["id"],)).fetchone():
                conn.execute("UPDATE out_variants SET paused=0 WHERE step_id=? AND arm=0", (row["id"],))   # never rest them all
        conn.commit()
        return cid
    conn.execute("DELETE FROM out_variants WHERE step_id IN (SELECT id FROM out_steps WHERE campaign_id=?)", (cid,))
    conn.execute("DELETE FROM out_steps WHERE campaign_id=?", (cid,))
    for pos, step in enumerate(doc.get("steps") or [], start=1):
        sid = conn.execute("INSERT INTO out_steps(campaign_id, position, gap_days, same_thread) VALUES(?,?,?,?)",
                           (cid, pos, 0 if pos == 1 else max(1, int(step.get("gap_days") or 3)),
                            int(step.get("same_thread", 1)))).lastrowid
        for arm, v in enumerate(step.get("versions") or []):
            conn.execute("INSERT INTO out_variants(step_id, arm, subject, body, paused) VALUES(?,?,?,?,?)",
                         (sid, arm, (v.get("subject") or "").strip(), v.get("body") or "", int(bool(v.get("paused")))))
    conn.commit()
    return cid


def variant_for(conn, campaign_id: int, position: int, arm: int):
    """A lead keeps one letter for the whole cadence. A step with fewer versions
    than the lead's letter wraps around, so a single-version follow-up reaches everyone."""
    vs = conn.execute("SELECT v.*, s.same_thread FROM out_variants v JOIN out_steps s ON s.id=v.step_id "
                      "WHERE s.campaign_id=? AND s.position=? ORDER BY v.arm", (campaign_id, position)).fetchall()
    own = next((v for v in vs if v["arm"] == arm and not v["paused"]), None)
    live = [v for v in vs if not v["paused"]] or vs          # a rested version's leads move to the ones still running
    return own or (live[arm % len(live)] if live else None)


def field_usage(conn, camp: dict) -> list[dict]:
    """For each email: which merge fields it uses, how many leads have nothing for each, and whether the
    email says what to write instead. Counted against the real audience, not a sample."""
    rows = audience(conn, camp["audience"], camp.get("id"))["rows"]
    values = [merge_values(conn, r["id"]) for r in rows]
    out = []
    for s in camp["steps"]:
        uses: dict[str, dict] = {}
        for v in s["versions"]:
            for m in FIELD_RE.finditer((v.get("subject") or "") + "\n" + (v.get("body") or "")):
                u = uses.setdefault(m.group(1), {"field": m.group(1), "fallback": m.group(2), "known": m.group(1) in FIELDS})
                if not m.group(2):
                    u["fallback"] = None                     # one bare use is enough to hold a lead
        for u in uses.values():
            u["empty"] = sum(1 for val in values if not val.get(u["field"])) if u["known"] else len(values)
        out.append({"position": s["position"], "fields": sorted(uses.values(), key=lambda u: -u["empty"]), "leads": len(values)})
    return out


def version_numbers(conn, cid: int) -> dict:
    """Per email and version: how many got it, and how many replied to THAT email."""
    out: dict = {}
    for r in conn.execute(
            "SELECT m.step_position p, v.arm arm, COUNT(*) sent, "
            " SUM(EXISTS(SELECT 1 FROM out_events x WHERE x.enrollment_id=m.enrollment_id AND x.kind='reply' AND x.step_position=m.step_position)) replied "
            "FROM out_messages m JOIN out_enrollments e ON e.id=m.enrollment_id JOIN out_variants v ON v.id=m.variant_id "
            "WHERE e.campaign_id=? AND m.state='sent' GROUP BY 1,2", (cid,)):
        out[f"{r['p']}.{r['arm']}"] = {"sent": r["sent"], "replied": r["replied"]}
    return out


def preflight(conn, camp: dict, settings: dict, inbox_ready: bool) -> list[dict]:
    """Everything worth knowing before pressing Launch, worst first. `block` stops the launch; `warn` is
    a decision for the person; `info` is simply what will happen."""
    import looks
    out = []
    add = lambda level, text, where="": out.append({"level": level, "text": text, "where": where})
    if not camp["steps"]:
        add("block", "Add at least one email.", "emails")
    for s in camp["steps"]:
        if not s["versions"]:
            add("block", f"Email {s['position']} has no version.", "emails")
        new_thread = s["position"] > 1 and not s.get("same_thread", 1)
        for v in s["versions"]:
            tag = f"Email {s['position']} version {'ABCD'[v['arm']]}"
            if not (v["body"] or "").strip():
                add("block", f"{tag} has no text.", "emails")
            if (s["position"] == 1 or new_thread) and not v["subject"]:
                add("block", f"{tag} needs a subject line.", "emails")
            for h in looks.hints(v["subject"] or "", v["body"] or "", s["position"], not new_thread):
                add("warn", f"{tag}: {h}", "emails")
    if not inbox_ready:
        add("block", "Connect the mailbox first.", "mailbox")
    if not settings["footer"].strip():
        add("block", "Add your sign-off footer (who you are and a postal address). Australian law requires it.", "mailbox")
    boxes = [m for m in mailboxes(conn)]
    for m in boxes:
        if m["status"] == "broken":
            add("warn", f"{m['email']} needs attention and will not send: {m['status_reason']}", "mailbox")
        report = json.loads(m["health"] or "{}")
        for it in report.get("items", []):
            if it["state"] == "bad" and it["name"] in ("SPF", "DKIM", "DMARC"):
                add("warn", f"{m['email']}: {it['says']} Mail from a domain without it is far more likely to land in spam.", "mailbox")
        if not report:
            add("warn", f"{m['email']} has not been checked yet. Run its health check once before a real campaign.", "mailbox")
    if camp["steps"] and all(s["versions"] for s in camp["steps"]):
        aud = audience(conn, camp["audience"], camp.get("id"))
        if not aud["count"]:
            add("block", "Nobody matches this audience.", "audience")
        held = unfillable(conn, camp)
        for f, n in held.items():
            add("warn", f"{n:,} leads have no {f} and an email uses it with no fallback, so they will be left out. "
                        f"Write {{{f}|something else}} to keep them.", "emails")
        if max(len(s["versions"]) for s in camp["steps"]) == 1:
            add("info", "One version only, so this campaign will not tell you what works better. Add a version B to the first email to compare.", "emails")
        if aud["count"]:
            pace = total_pace(conn)
            f = forecast(pace, aud["count"], [s["gap_days"] or 3 for s in camp["steps"][1:]], 0, camp.get("weekdays") or "1,2,3,4,5")
            add("info", f"{aud['count']:,} businesses. At today's limits ({pace['ramp_start']} a day, growing to {pace['daily_cap']}) the first "
                        f"email reaches everyone in about {f['days_to_first_touch_all']} days and the series ends in about {f['days_to_finish']}.", "audience")
    order = {"block": 0, "warn": 1, "info": 2}
    return sorted(out, key=lambda o: order[o["level"]])


def launch_problems(conn, camp: dict, settings: dict, have_password: bool) -> list[str]:
    problems = []
    if not camp["steps"]:
        problems.append("Add at least one email.")
    for s in camp["steps"]:
        for v in s["versions"]:
            tag = f"Email {s['position']} version {'ABCD'[v['arm']]}"
            if not (v["body"] or "").strip():
                problems.append(f"{tag} has no text.")
            if s["position"] == 1 and not v["subject"]:
                problems.append(f"{tag} needs a subject line.")
        if not s["versions"]:
            problems.append(f"Email {s['position']} has no version.")
    if not (settings["from_email"] and have_password):
        problems.append("Connect the mailbox first.")
    if not settings["footer"].strip():
        problems.append("Add your sign-off footer (who you are and a postal address). Australian law requires it.")
    return problems


def unfillable(conn, camp: dict) -> dict:
    """Before launch: how many leads have nothing for a merge field that some version uses
    without a fallback. They would be left out, so say so while it can still be fixed."""
    texts = [v["subject"] + "\n" + v["body"] for s in camp["steps"] for v in s["versions"]]
    bare = {m.group(1) for t in texts for m in FIELD_RE.finditer(t) if not m.group(2) and m.group(1) in FIELDS}
    if not bare:
        return {}
    counts = Counter()
    for r in audience(conn, camp["audience"], camp["id"])["rows"]:
        values = merge_values(conn, r["id"])
        counts.update(f for f in bare if not values.get(f))
    return dict(counts)


def launch(conn, cid: int, start_at: datetime, check_domains=check_mx, first: int | None = None) -> dict:
    """Start the campaign, or add more leads to one that is running. `first` = only that many for now
    (a careful start: send to 20, read the replies, then send to the rest with the same call)."""
    camp = load_campaign(conn, cid)
    already = {r[0] for r in conn.execute("SELECT contact_id FROM out_enrollments WHERE campaign_id=?", (cid,))}
    limit = int(camp["audience"].get("max_leads") or 0)
    limit = max(0, limit - len(already)) if limit else 0
    limit = min(limit, first) if (limit and first) else (first or limit)
    everyone = [r for r in audience(conn, dict(camp["audience"], max_leads=0), cid)["rows"] if r["id"] not in already]

    # A lead has to work in EVERY version before letters are handed out. Dropping it from
    # one version only would leave that version with a different kind of lead, and the
    # comparison would be measuring the leads, not the emails.
    texts = [v["subject"] + "\n" + v["body"] for s in camp["steps"] for v in s["versions"]]
    skipped, usable = Counter(), []
    for r in everyone:
        bad = {f for t in texts for f in render(t, merge_values(conn, r["id"]))[1]}
        if bad:
            skipped["no " + ", ".join(sorted(bad))] += 1
        else:
            usable.append(r)
    usable_all = list(usable)
    if limit and len(usable) > limit:
        usable = random.Random(cid).sample(usable, limit)
    if check_domains:
        check_domains(conn, [r["id"] for r in usable])
        dead = {r[0] for r in conn.execute("SELECT id FROM out_contacts WHERE mx_status='none'")}
        if any(r["id"] in dead for r in usable):
            skipped["domain does not accept mail"] = sum(r["id"] in dead for r in usable)
        usable = [r for r in usable if r["id"] not in dead]
    strata = defaultdict(list)
    for r in usable:
        strata[(r["trade"], r["state"])].append(r)
    n_arms = max(len(s["versions"]) for s in camp["steps"])
    rng, ready, k = random.Random(cid + len(already)), [], len(already)     # a later batch carries the rotation on
    for key in sorted(strata, key=str):
        rng.shuffle(strata[key])
        for r in strata[key]:          # round robin inside each trade+state keeps the versions comparable
            ready.append((r, k % n_arms))
            k += 1
    rng.shuffle(ready)                 # send order interleaves versions, trades and states
    stamp = iso(now_utc())
    for r, arm in ready:
        conn.execute("INSERT OR IGNORE INTO out_enrollments(campaign_id, contact_id, arm, next_due, enrolled_at) "
                     "VALUES(?,?,?,?,?)", (cid, r["id"], arm, iso(start_at), stamp))
    conn.execute("UPDATE out_campaigns SET status='active', launched_at=COALESCE(launched_at, ?), start_at=COALESCE(start_at, ?) WHERE id=?",
                 (stamp, iso(start_at), cid))
    conn.commit()
    return {"enrolled": len(ready), "left_out": dict(skipped), "still_waiting": waiting(conn, cid)}


def waiting(conn, cid: int) -> int:
    """Businesses that match a running campaign and have not been added to it yet (after a careful first batch)."""
    camp = load_campaign(conn, cid)
    already = {r[0] for r in conn.execute("SELECT contact_id FROM out_enrollments WHERE campaign_id=?", (cid,))}
    left = len([r for r in audience(conn, dict(camp["audience"], max_leads=0), cid)["rows"] if r["id"] not in already])
    cap = int(camp["audience"].get("max_leads") or 0)
    return min(left, max(0, cap - len(already))) if cap else left


# ── sending capacity ────────────────────────────────────────────────────────

def cap_for(settings: dict, first_send: datetime | None, now: datetime) -> int:
    days = (now - first_send).days if first_send else 0
    return int(min(settings["daily_cap"], settings["ramp_start"] + settings["ramp_step"] * days))


def first_send_at(conn) -> datetime | None:
    r = conn.execute("SELECT MIN(sent_at) FROM out_messages").fetchone()[0]
    return parse_iso(r) if r else None


def forecast(settings: dict, leads: int, gaps: list[int], days_already: int = 0, weekdays: str = "1,2,3,4,5") -> dict:
    """Follow-ups go first, new leads take what is left of the day's limit. gaps[i] is the wait, in
    SENDING days, before email i+2. Assumes nobody replies, so it is the slowest case."""
    per_week = len([d for d in (weekdays or "").split(",") if d]) or 5
    owed: dict[int, Counter] = defaultdict(Counter)      # sending day -> {email number: how many are due}
    waiting, day, last_first = leads, 0, 0
    while (waiting or owed) and day < 3000:
        cap = int(min(settings["daily_cap"], settings["ramp_start"] + settings["ramp_step"] * (days_already + day * 7 // per_week)))
        due = Counter()
        for d in [k for k in owed if k <= day]:
            due.update(owed.pop(d))
        for step in sorted(due):
            n = min(cap, due[step])
            cap -= n
            if n and step - 1 < len(gaps):
                owed[day + gaps[step - 1]][step + 1] += n
            if due[step] - n:
                owed[day + 1][step] += due[step] - n
        n = min(cap, waiting)
        waiting -= n
        if n:
            last_first = day
            if gaps:
                owed[day + gaps[0]][2] += n
        day += 1
    to_calendar = lambda d: math.ceil(d * 7 / per_week)
    return {"days_to_first_touch_all": to_calendar(last_first + 1), "days_to_finish": to_calendar(day), "leads": leads}


# ── results ─────────────────────────────────────────────────────────────────

def wilson(hits: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z, p = 1.96, hits / n
    mid = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, mid - half), min(1.0, mid + half)


def results(conn, cid: int) -> dict:
    arms = []
    for r in conn.execute(
            "SELECT e.arm, COUNT(*) enrolled, "
            " SUM(EXISTS(SELECT 1 FROM out_messages m WHERE m.enrollment_id=e.id)) contacted, "
            " SUM(e.status='bounced') bounced, SUM(e.status='replied') replied, "
            " SUM(e.status='unsubscribed') unsubscribed, SUM(e.outcome='positive') positive "
            "FROM out_enrollments e WHERE e.campaign_id=? GROUP BY e.arm ORDER BY e.arm", (cid,)):
        d = dict(r)
        d["delivered"] = d["contacted"] - d["bounced"]
        d["reply_low"], d["reply_high"] = wilson(d["replied"], d["delivered"])
        arms.append(d)

    verdict = "Nothing sent yet."
    live = [a for a in arms if a["delivered"]]
    if len(live) == 1:
        verdict = "One version only, so there is nothing to compare."
    elif live:
        lead = max(live, key=lambda a: a["replied"] / a["delivered"])
        rest = [a for a in live if a is not lead]
        if all(lead["reply_low"] > a["reply_high"] for a in rest):
            verdict = f"Version {'ABCD'[lead['arm']]} is ahead, and the gap is bigger than chance explains."
        else:
            p1 = lead["replied"] / lead["delivered"]
            p2 = max(a["replied"] / a["delivered"] for a in rest)
            pbar, gap = (p1 + p2) / 2, p1 - p2
            verdict = "Too early to call."
            if gap > 0:
                need = math.ceil(16 * pbar * (1 - pbar) / (gap * gap))
                verdict += f" A gap this size needs about {need:,} delivered emails per version to be trusted."

    steps = [dict(r) for r in conn.execute(
        "SELECT m.step_position position, COUNT(*) sent, "
        " (SELECT COUNT(*) FROM out_events v JOIN out_enrollments e2 ON e2.id=v.enrollment_id "
        "   WHERE e2.campaign_id=? AND v.kind='reply' AND v.step_position=m.step_position) replies, "
        " (SELECT COUNT(*) FROM out_events v JOIN out_enrollments e2 ON e2.id=v.enrollment_id "
        "   WHERE e2.campaign_id=? AND v.kind='bounce_hard' AND v.step_position=m.step_position) bounces "
        "FROM out_messages m JOIN out_enrollments e ON e.id=m.enrollment_id WHERE e.campaign_id=? "
        "GROUP BY m.step_position ORDER BY m.step_position", (cid, cid, cid))]

    feed = [dict(r) for r in conn.execute(
        "SELECT v.id, v.kind, v.at, v.detail, v.step_position, e.id enrollment_id, e.arm, e.outcome, c.email, b.name "
        "FROM out_events v JOIN out_enrollments e ON e.id=v.enrollment_id JOIN out_contacts c ON c.id=e.contact_id "
        "JOIN businesses b ON b.place_id=c.place_id WHERE e.campaign_id=? AND v.kind<>'sent' "
        "ORDER BY v.at DESC LIMIT 200", (cid,))]
    status = {r[0]: r[1] for r in conn.execute("SELECT status, COUNT(*) FROM out_enrollments WHERE campaign_id=? "
                                               "GROUP BY status", (cid,))}
    return {"arms": arms, "verdict": verdict, "steps": steps, "feed": feed, "status": status}


def summaries(conn) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT c.id, c.name, c.status, c.start_at, c.created_at, "
        " (SELECT COUNT(*) FROM out_enrollments e WHERE e.campaign_id=c.id) enrolled, "
        " (SELECT COUNT(*) FROM out_messages m JOIN out_enrollments e ON e.id=m.enrollment_id "
        "   WHERE e.campaign_id=c.id) sent, "
        " (SELECT COUNT(*) FROM out_enrollments e WHERE e.campaign_id=c.id AND e.status='replied') replied, "
        " (SELECT COUNT(*) FROM out_enrollments e WHERE e.campaign_id=c.id AND e.status='bounced') bounced "
        "FROM out_campaigns c ORDER BY c.id DESC")]


# ── the leads board ─────────────────────────────────────────────────────────

def clean_email(raw: str | None) -> str:
    return unquote(raw or "").strip().lower()


def pick_for_campaign(conn, place_ids: list[str], name: str) -> dict:
    """Leads chosen on the board become a draft campaign. A listing maps to its inbox, so ten
    listings of one chain are still one contact."""
    conn.execute("CREATE TEMP TABLE IF NOT EXISTS _ids(place_id TEXT PRIMARY KEY)")
    conn.execute("DELETE FROM _ids")
    conn.executemany("INSERT OR IGNORE INTO _ids VALUES(?)", [(i,) for i in place_ids])
    emails = {clean_email(r[0]) for r in conn.execute(
        "SELECT email FROM businesses WHERE place_id IN (SELECT place_id FROM _ids) AND COALESCE(email,'') <> ''")}
    ids = [r[0] for r in conn.execute("SELECT id, email FROM out_contacts") if r[1] in emails]
    if not ids:
        return {"error": "None of those leads has an email address yet."}
    cid = save_campaign(conn, {"name": name, "audience": {"picked": True, "include_shared": True}, "steps": [
        {"versions": [{"subject": "", "body": "Hi {short_name|there},\n\n"}, {"subject": "", "body": "Hi {short_name|there},\n\n"}]},
        {"gap_days": 3, "versions": [{"subject": "", "body": ""}]}]})
    conn.executemany("INSERT OR IGNORE INTO out_picked VALUES(?,?)", [(cid, i) for i in ids])
    conn.commit()
    return {"id": cid, "picked": len(place_ids), "inboxes": len(ids)}


def outreach_by_place(conn) -> dict:
    """What has happened by email, per listing: {place_id: {status, campaign, emails_sent, last_email_at, at}}.
    Read by the board (a column and a filter) and by the automatic stages."""
    rank = {"queued": 0, "contacted": 1, "no reply": 2, "replied": 3, "unsubscribed": 3, "bounced": 3}
    by_email: dict[str, dict] = {}
    for r in conn.execute(
            "SELECT c.email, e.status, k.name campaign, COUNT(m.id) sent, MAX(m.sent_at) last_sent, "
            " (SELECT MAX(at) FROM out_events v WHERE v.enrollment_id=e.id) last_event "
            "FROM out_enrollments e JOIN out_contacts c ON c.id=e.contact_id JOIN out_campaigns k ON k.id=e.campaign_id "
            "LEFT JOIN out_messages m ON m.enrollment_id=e.id GROUP BY e.id"):
        status = {"replied": "replied", "bounced": "bounced", "unsubscribed": "unsubscribed",
                  "finished": "no reply"}.get(r["status"], "contacted" if r["sent"] else "queued")
        row = {"status": status, "campaign": r["campaign"], "emails_sent": r["sent"], "last_email_at": r["last_sent"],
               "at": r["last_event"] or r["last_sent"]}
        if r["email"] not in by_email or rank[status] >= rank[by_email[r["email"]]["status"]]:
            by_email[r["email"]] = row
    if not by_email:
        return {}
    return {r["place_id"]: by_email[e] for r in conn.execute("SELECT place_id, email FROM businesses WHERE COALESCE(email,'') <> ''")
            if (e := clean_email(r["email"])) in by_email}


def board_annotations(conn, pipeline: list[str], closed: list[str], auto_stages: dict) -> dict:
    """Stages and notes for the board. Sending moves a lead forward on its own (queued, contacted,
    replied) but never backward, never out of a closed stage such as Won, and never over a stage
    a person set after the email event happened."""
    ann = {r["place_id"]: json.loads(r["json"]) for r in conn.execute("SELECT place_id, json FROM board_annotations")}
    order = {name: i for i, name in enumerate(pipeline)}
    for place_id, o in (outreach_by_place(conn) if auto_stages else {}).items():
        target = auto_stages.get({"no reply": "contacted"}.get(o["status"], o["status"]))
        if target not in order:
            continue
        a = ann.get(place_id) or {}
        current = a.get("stage") or (pipeline[0] if pipeline else None)
        by_hand_later = a.get("stage_by") == "hand" and (a.get("updated_at") or "") >= (o["at"] or "")[:19]
        if current in closed or by_hand_later or order[target] <= order.get(current, -1):
            continue
        ann[place_id] = {**a, "stage": target, "stage_by": "auto", "updated_at": (o["at"] or "")[:19]}
    return ann


def save_annotation(conn, place_id: str, annotation: dict) -> None:
    conn.execute("INSERT INTO board_annotations(place_id, json, updated_at) VALUES(?,?,?) "
                 "ON CONFLICT(place_id) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at",
                 (place_id, json.dumps(annotation), iso(now_utc())))
    conn.commit()


def import_board_file(conn) -> int:
    """One time: stages saved by the old stand-alone board (dashboard/annotations.json) move into the database."""
    path = _ctx.project / "dashboard" / "annotations.json"
    if conn.execute("SELECT 1 FROM board_annotations LIMIT 1").fetchone() or not path.exists():
        return 0
    found = json.loads(path.read_text()).get("annotations", {})
    for place_id, a in found.items():
        if isinstance(a.get("notes"), str):      # the old file kept a note as plain text; the board wants dated notes
            a["notes"] = [{"t": (a.get("updated_at") or "")[:19], "text": a["notes"]}] if a["notes"] else []
        conn.execute("INSERT OR IGNORE INTO board_annotations VALUES(?,?,?)", (place_id, json.dumps(a), a.get("updated_at")))
    conn.commit()
    return len(found)
