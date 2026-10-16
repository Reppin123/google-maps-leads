"""ask.py: describe what you need; the assistant prepares it and you confirm.

The model is an operator with a short, fixed set of tools. It can look at the project and it
can PREPARE things: a search plan, a draft campaign, a find-emails job. Anything that touches
the outside world comes back to the screen as a card with a button, and only the person's
click runs it, through the same endpoints the forms use. There is no tool that starts a
scrape, launches a campaign or sends an email, so no wording of a request can make it do so.

A hand-written loop rather than the SDK's beta tool runner: this ships inside a product, so it
stays on the stable Messages endpoint, and the self-test swaps in a scripted client.
The whole app works with no key at all; this tab is the only part that needs one.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess

import runs
import store

MODEL = "claude-opus-5"
MAX_TURNS = 12
KEYCHAIN = ("maps-leads", "anthropic-api-key")        # person level: one key for every project

SYSTEM = """You operate a lead-finding and email outreach tool for the person you are talking to. \
You are working inside one project: {name} (country {country}). Each project is a separate client or purpose \
with its own data; never assume anything about other projects.

What you can do is set by your tools. You can read the project, and you can prepare three things for the \
person to approve: a Google Maps search plan, a draft email campaign, and a find-emails job. Preparing something \
puts a card with a button on their screen. Nothing runs until they press it, and you have no way to press it, \
so never say a search has started, a campaign has launched or an email was sent. Say what you prepared and \
what pressing the button will do.

Searching: one search phrase finds roughly a quarter of the businesses that exist, because Google Maps matches \
wording. Unless told otherwise, plan three or four phrasings of the same idea (the trade, a common synonym, the \
service a customer would type). For a first look at a new kind of business, offer a quick sample.

Campaign drafts: plain text, short, one clear question, written the way a person writes to another person. \
No hype. Merge fields are {{name}}, {{short_name}}, {{suburb}}, {{state}}, {{trade}}, {{rating}}, {{reviews}}, \
{{website}}; write a fallback for any field that can be empty, like {{suburb|your area}}. Give the first email \
two versions that differ in ONE thing, so the comparison means something. A blank subject on a follow-up sends \
it as a reply in the same thread. The footer and the unsubscribe line are added automatically; do not write them.

Answer in plain language, briefly. Use numbers from your tools, never from memory. If a tool returns an error, \
say what it means and what to try."""

TOOLS = [
    {"name": "project_overview",
     "description": "Counts for this project: businesses, how many have an email, the breakdown by search/trade and by "
                    "state, campaigns and their results, and any job running now. Call this first when the person asks "
                    "about their data or before drafting a campaign audience.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "query_leads",
     "description": "Run one read-only SQL SELECT over the project database and get up to 50 rows back. Main table: "
                    "businesses(place_id, name, suburb, state, primary_category, profile, phone, website, email, rating, "
                    "review_count, signal_score, has_website). Also out_contacts, out_campaigns, out_enrollments, "
                    "out_events. Use it for questions the overview does not answer.",
     "input_schema": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"],
                      "additionalProperties": False}},
    {"name": "plan_search",
     "description": "Prepare a Google Maps search and show the person the plan card (area covered, number of map "
                    "searches, time). Makes no requests to Google. The person starts it with the button on the card.",
     "input_schema": {"type": "object", "properties": {
         "phrases": {"type": "array", "items": {"type": "string"}, "description": "search phrases, run one after another"},
         "country": {"type": "string", "description": "two-letter country code"},
         "near": {"type": "string", "description": "a city or town to centre on; omit for the whole country"},
         "radius_km": {"type": "number"},
         "sample": {"type": "boolean", "description": "true = only 4 map searches, about a minute, to see what comes back"}},
         "required": ["phrases", "country"], "additionalProperties": False}},
    {"name": "propose_find_emails",
     "description": "Show a card offering to visit the websites of businesses that have not been checked yet and read "
                    "the contact emails published there. Returns how many websites are waiting.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "draft_campaign",
     "description": "Save a DRAFT email campaign for the person to review and edit. A draft sends nothing; only the "
                    "person can launch it, from the campaign page. Returns how many inboxes the audience matches and "
                    "any merge-field problems.",
     "input_schema": {"type": "object", "properties": {
         "name": {"type": "string"},
         "audience": {"type": "object", "properties": {
             "trades": {"type": "array", "items": {"type": "string"}, "description": "exact values from project_overview"},
             "states": {"type": "array", "items": {"type": "string"}},
             "min_rating": {"type": "number"}, "min_reviews": {"type": "number"},
             "website": {"type": "string", "enum": ["yes", "no"]},
             "max_leads": {"type": "integer"}}, "additionalProperties": False},
         "emails": {"type": "array", "description": "the series, first email first", "items": {"type": "object", "properties": {
             "gap_days": {"type": "integer", "description": "days after the previous email; ignored for the first"},
             "versions": {"type": "array", "items": {"type": "object", "properties": {
                 "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["subject", "body"],
                 "additionalProperties": False}}}, "required": ["versions"], "additionalProperties": False}}},
         "required": ["name", "audience", "emails"], "additionalProperties": False}},
    {"name": "job_status",
     "description": "Progress of searches and find-emails jobs in this project: state, businesses found, searches done.",
     "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}},
]

_conversations: dict[tuple[str, str], list] = {}


# ── the key ─────────────────────────────────────────────────────────────────

def save_key(key: str) -> None:
    subprocess.run(["security", "add-generic-password", "-U", "-s", KEYCHAIN[0], "-a", KEYCHAIN[1], "-w", key.strip()],
                   check=True, capture_output=True)


def load_key() -> str | None:
    r = subprocess.run(["security", "find-generic-password", "-s", KEYCHAIN[0], "-a", KEYCHAIN[1], "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() or None if r.returncode == 0 else None


def make_client():
    import anthropic
    key = load_key()
    return anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()   # else the environment or an `ant` profile


# ── tools ───────────────────────────────────────────────────────────────────

def _read_only(conn_path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{conn_path}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
    conn.set_authorizer(lambda action, *_: sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
    return conn


def run_tool(conn, name: str, args: dict, cards: list) -> dict:
    if name == "project_overview":
        one = lambda q: conn.execute(q).fetchone()[0]
        cols = {r[1] for r in conn.execute("PRAGMA table_info(businesses)")}
        return {"businesses": one("SELECT COUNT(*) FROM businesses"),
                "with_email": one("SELECT COUNT(*) FROM businesses WHERE COALESCE(email,'')<>''") if "email" in cols else 0,
                "inboxes_ready_to_email": one("SELECT COUNT(*) FROM out_contacts WHERE check_status='ok'"),
                "by_trade": [dict(r) for r in conn.execute(
                    "SELECT trade, COUNT(*) inboxes FROM out_contacts WHERE check_status='ok' GROUP BY trade ORDER BY 2 DESC LIMIT 25")],
                "by_state": [dict(r) for r in conn.execute(
                    "SELECT state, COUNT(*) inboxes FROM out_contacts WHERE check_status='ok' GROUP BY state ORDER BY 2 DESC")],
                "campaigns": store.summaries(conn), "websites_not_checked_for_email": runs.enrich_todo(conn),
                "inboxes_connected": [m["email"] for m in store.mailboxes(conn)],
                "jobs_running": [r["label"] for r in runs.list_runs(conn) if r["state"] == "running"]}
    if name == "query_leads":
        ro = _read_only(store.PROJECT / "leads.db")
        try:
            cur = ro.execute(args["sql"])
            rows = [dict(r) for r in cur.fetchmany(50)]
            return {"rows": rows, "more_rows_not_shown": cur.fetchone() is not None}
        finally:
            ro.close()
    if name == "plan_search":
        plan = runs.plan({**args, "country": (args.get("country") or store.CONF["country"]).upper()})
        if not plan.get("error"):
            cards.append({"type": "plan", "plan": plan})
        return {k: v for k, v in plan.items() if k != "request"}
    if name == "propose_find_emails":
        todo = runs.enrich_todo(conn)
        if todo:
            cards.append({"type": "enrich", "todo": todo})
        return {"websites_waiting": todo}
    if name == "draft_campaign":
        steps = [{"gap_days": e.get("gap_days") or 3, "versions": e["versions"][:4]} for e in args["emails"][:6]]
        cid = store.save_campaign(conn, {"name": args["name"], "audience": args.get("audience") or {}, "steps": steps})
        camp = store.load_campaign(conn, cid)
        count = store.audience(conn, camp["audience"], cid)["count"]
        cards.append({"type": "campaign", "id": cid, "name": args["name"], "inboxes": count})
        return {"saved_as_draft": True, "inboxes_matching": count, "leads_with_an_empty_merge_field": store.unfillable(conn, camp),
                "note": "Nothing is sent. The person reviews, edits and launches it from the campaign page."}
    if name == "job_status":
        return {"jobs": [{k: r.get(k) for k in ("label", "kind", "state", "progress", "last_line")} for r in runs.list_runs(conn)[:8]]}
    raise ValueError(f"no such tool: {name}")


# ── the loop ────────────────────────────────────────────────────────────────

def ask(conn, conversation_id: str, text: str, client=None) -> dict:
    client = client or make_client()
    history = _conversations.setdefault((store.PROJECT.name, conversation_id), [])
    history.append({"role": "user", "content": text})
    cards: list = []
    system = SYSTEM.format(name=store.CONF["name"], country=store.CONF["country"] or "not set")
    for _ in range(MAX_TURNS):
        response = client.messages.create(model=MODEL, max_tokens=16000, system=system, tools=TOOLS, messages=history,
                                          thinking={"type": "adaptive"}, output_config={"effort": "medium"})
        history.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "refusal":
            return {"reply": "I can't help with that request.", "cards": cards}
        if response.stop_reason != "tool_use":
            break
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                out, failed = run_tool(conn, block.name, dict(block.input), cards), False
            except Exception as e:                       # the model reads the error and can correct itself
                out, failed = {"error": f"{type(e).__name__}: {e}"}, True
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out, default=str)[:20000],
                            "is_error": failed})
        history.append({"role": "user", "content": results})      # every result in ONE message
    reply = "\n\n".join(b.text for b in response.content if b.type == "text").strip()
    if response.stop_reason == "max_tokens":
        reply += "\n\n(That answer was cut short. Ask me to continue.)"
    return {"reply": reply or "Done.", "cards": cards}
