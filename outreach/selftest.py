"""selftest.py: runs a whole campaign against a throwaway database with a fake clock,
a fake outbox and real-shaped inbound mail (a Gmail bounce report, an Exchange-style
bounce with no thread headers, an out-of-office, a reply, an unsubscribe). Never
touches leads.db and never opens a network connection."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import mailer
import store

from pipeline import SCHEMA as LEADS_SCHEMA  # noqa: E402  (store put leads/ on the path)

ME = "sam@sender-test.com.au"
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str) -> None:
    results.append((bool(ok), label))
    print(("  ok    " if ok else "  FAIL  ") + label)


class Outbox:
    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)


def seed(conn) -> None:
    conn.executescript(LEADS_SCHEMA)
    for col in ("email TEXT", "social_facebook TEXT", "enrich_status TEXT"):
        conn.execute(f"ALTER TABLE businesses ADD COLUMN {col}")
    rows = []
    trades = ["Plumbers", "Painters & decorators"]
    states = [("NSW", "Bondi"), ("VIC", "Fitzroy"), ("WA", "Fremantle")]
    n = 0
    for trade in trades:
        for state, suburb in states:
            for i in range(8):
                n += 1
                rows.append((f"p{n}", f"Lead {n} {trade.split()[0]} Pty Ltd | {suburb}", suburb if i else None, state,
                             trade, f"https://lead{n}.com.au", f"info@lead{n}.com.au", 10 + n))
    for i in range(5):      # a franchise: one inbox, its own domain, five listings
        rows.append((f"f{i}", f"Fox Mowing {i}", "Ryde", "NSW", "Plumbers", "https://foxmow.com.au", "fox@foxmow.com.au", i))
    for i in range(4):      # a theme author's address left on four unrelated sites
        rows.append((f"t{i}", f"Themed {i}", "Ryde", "NSW", "Plumbers", f"https://themed{i}.com.au", "fontguy@gmail.com", 1))
    rows.append(("j1", "Junk", "Ryde", "NSW", "Plumbers", "https://junk.com.au", "support@webador.com", 1))
    rows.append(("j2", "Bad", "Ryde", "NSW", "Plumbers", "https://bad.com.au", "admin@bad..au", 1))
    rows.append(("j3", "Spacey", "Ryde", "NSW", "Roofers", "https://spacey.com.au", "%20info@spacey.com.au", 1))
    rows.append(("g1", "Council", "Ryde", "NSW", "Plumbers", "https://ryde.nsw.gov.au", "works@ryde.nsw.gov.au", 1))
    for pid, name, suburb, state, trade, site, email_addr, reviews in rows:
        conn.execute("INSERT INTO businesses(place_id, name, suburb, state, profile, website, email, review_count, "
                     "rating, has_website, signal_score) VALUES(?,?,?,?,?,?,?,?,4.6,1,3)",
                     (pid, name, suburb, state, trade, site, email_addr, reviews))
    conn.commit()


def reply_to(sent, body, subject=None, sender=None, headers=None) -> bytes:
    m = EmailMessage()
    m["From"] = sender or sent["To"]
    m["To"] = ME
    m["Subject"] = subject or "Re: " + sent["Subject"]
    m["Message-ID"] = f"<in-{abs(hash((body, str(sent['To']))))}@their.host>"
    m["In-Reply-To"] = sent["Message-ID"]
    m["References"] = sent["Message-ID"]
    for k, v in (headers or {}).items():
        m[k] = v
    m.set_content(f"{body}\n\nOn Mon, 21 Sep 2026 at 10:02, Sam <{ME}> wrote:\n> unsubscribe and I won't email again\n")
    return m.as_bytes()


def gmail_bounce(sent, status="5.1.1", threaded=True) -> bytes:
    """Shaped like the report Gmail really sends: multipart/report with the original attached."""
    to = str(sent["To"])
    original = f"Message-ID: {sent['Message-ID']}\r\nTo: {to}\r\nSubject: {sent['Subject']}\r\n\r\nbody\r\n"
    thread = (f"In-Reply-To: {sent['Message-ID']}\r\nReferences: {sent['Message-ID']}\r\n"
              f"X-Failed-Recipients: {to}\r\n") if threaded else ""
    sender = "Mail Delivery Subsystem <mailer-daemon@googlemail.com>" if threaded else "postmaster@outlook.example"
    action = "failed" if status.startswith("5") else "delayed"
    return (f"From: {sender}\r\nTo: {ME}\r\nSubject: Delivery Status Notification ({action.title()})\r\n"
            f"Message-ID: <dsn-{abs(hash((to, status)))}@mx.google.com>\r\n{thread}"
            f"Content-Type: multipart/report; boundary=\"BB\"; report-type=delivery-status\r\n\r\n"
            f"--BB\r\nContent-Type: text/plain\r\n\r\nAddress not found. The response was: 550 {status} no such user\r\n"
            f"--BB\r\nContent-Type: message/delivery-status\r\n\r\nReporting-MTA: dns; googlemail.com\r\n\r\n"
            f"Final-Recipient: rfc822; {to}\r\nAction: {action}\r\nStatus: {status}\r\n\r\n"
            f"--BB\r\nContent-Type: message/rfc822\r\n\r\n{original}\r\n--BB--\r\n").encode()


def words(m) -> str:
    """The text part of an email we sent (it now has an HTML twin)."""
    return m.get_body(("plain",)).get_content()


def drain(conn, outbox, now) -> list[str]:
    said = []
    for _ in range(400):
        out = mailer.send_one(conn, outbox, now)
        said.append(out)
        if not out.startswith("sent"):
            break
    return said


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    os.environ["MAPS_LEADS_HOME"] = str(tmp / "shared-home")      # never the real shared list
    (tmp / "project.json").write_text('{"name": "Self-test", "country": "AU", "default_tz": "Australia/Sydney"}')
    (tmp / "dashboard.spec.json").write_text('{"junk_email_domains": ["webador.com"]}')
    store.use(tmp)
    conn = store.connect()
    seed(conn)
    conn.executescript("CREATE TABLE campaigns(id INTEGER); CREATE TABLE templates(id INTEGER); "
                       "INSERT INTO templates VALUES(1);")

    print("tables and contacts")
    dropped = store.migrate(conn)
    check(dropped == ["campaigns"], "an empty legacy table is dropped, one holding data is left alone")
    counts = store.sync_contacts(conn)
    status = {r["email"]: r for r in conn.execute("SELECT * FROM out_contacts")}
    check(status["fox@foxmow.com.au"]["places"] == 5 and status["fox@foxmow.com.au"]["check_status"] == "ok",
          "a franchise inbox on its own domain is one contact covering 5 listings")
    check(status["fontguy@gmail.com"]["check_status"] == "placeholder",
          "one inbox on four unrelated websites is treated as a placeholder")
    check(status["support@webador.com"]["check_status"] == "placeholder", "site-builder address is a placeholder")
    check(status["admin@bad..au"]["check_status"] == "bad_syntax", "malformed address is caught")
    check(status["info@spacey.com.au"]["check_status"] == "ok", "a '%20' left by the crawl is cleaned off, not thrown away")
    check(status["works@ryde.nsw.gov.au"]["check_status"] == "gov_edu", "government address is kept out")
    check(status["info@lead20.com.au"]["tz"] == "Australia/Perth", "a WA lead gets Perth time")
    check(store.sync_contacts(conn) == counts and len(status) == conn.execute(
        "SELECT COUNT(*) FROM out_contacts").fetchone()[0], "re-running the contact sync changes nothing")

    print("audience and launch")
    store.set_settings(conn, {"from_name": "Sam", "from_email": ME, "footer": "Sam, Sender Co\n1 Test St, Sydney NSW",
                              "gap_min": 0, "gap_max": 0, "ramp_start": 30, "daily_cap": 30, "ramp_step": 0,
                              "bounce_pause_pct": 10})     # 2 bounces in 30 would trip the real 4% guard early
    doc = {"name": "Self-test", "audience": {"trades": ["Plumbers", "Painters & decorators"]},
           "steps": [
               {"versions": [{"subject": "Quick question for {short_name}", "body": "Hi {short_name}, A in {suburb|your area}."},
                             {"subject": "{short_name}: missed calls?", "body": "Hi {short_name}, B in {suburb|your area}."}]},
               {"gap_days": 3, "versions": [{"subject": "", "body": "Following up, {short_name}."}]},
               {"gap_days": 4, "versions": [{"subject": "", "body": "Last one A."}, {"subject": "", "body": "Last one B."}]}]}
    cid = store.save_campaign(conn, doc)
    aud = store.audience(conn, doc["audience"], cid)
    check(aud["count"] == 48 and aud["excluded"].get("One inbox shared by more than 3 listings (chains)") == 1
          and aud["excluded"].get("Address looks wrong or is a website-builder placeholder") == 4,
          f"audience is 48 with every exclusion named ({aud['excluded']})")
    camp = store.load_campaign(conn, cid)
    check(store.launch_problems(conn, camp, store.get_settings(conn), False) == ["Connect the mailbox first."],
          "launch is blocked until the mailbox is connected")
    bad = dict(doc, steps=[{"versions": [{"subject": "Hi", "body": "Hi {suburb}"}, {"subject": "Hi", "body": "Hi"}]}],
               name="no fallback in version A only")
    bad_id = store.save_campaign(conn, bad)
    monday = datetime(2026, 9, 21, 0, 30, tzinfo=timezone.utc)      # 10:30 Sydney, 08:30 Perth
    out = store.launch(conn, bad_id, monday, check_domains=None)
    check(out["enrolled"] == 42 and out["left_out"] == {"no suburb": 6},
          "leads with an empty merge field and no fallback are held back, never sent 'Hi ,'")
    split = [r[0] for r in conn.execute("SELECT COUNT(*) FROM out_enrollments WHERE campaign_id=? GROUP BY arm", (bad_id,))]
    check(split == [21, 21], f"a lead that fails in one version is left out of all of them, so the split stays even ({split})")
    conn.execute("DELETE FROM out_enrollments WHERE campaign_id=?", (bad_id,))
    conn.execute("UPDATE out_campaigns SET status='draft' WHERE id=?", (bad_id,))
    out = store.launch(conn, cid, monday, check_domains=None)
    arms = dict(conn.execute("SELECT arm, COUNT(*) FROM out_enrollments WHERE campaign_id=? GROUP BY arm", (cid,)).fetchall())
    check(out["enrolled"] == 48 and arms == {0: 24, 1: 24}, f"48 leads split evenly across versions ({arms})")
    per = conn.execute("SELECT MAX(n)-MIN(n) FROM (SELECT COUNT(*) n FROM out_enrollments e JOIN out_contacts c "
                       "ON c.id=e.contact_id WHERE e.campaign_id=? GROUP BY c.trade, c.state, e.arm)", (cid,)).fetchone()[0]
    check(per == 0, "each trade and state is split evenly too, so versions are compared like for like")

    print("sending")
    outbox = Outbox()
    check(mailer.send_one(conn, outbox, monday - timedelta(hours=1)) == "nothing due right now",
          "nothing goes before the scheduled start")
    said = drain(conn, outbox, monday)
    check(len(outbox.sent) == 30 and said[-1] == "today's limit reached (30)", "the daily limit stops sending at 30")
    perth = [m for m in outbox.sent if "Fremantle" in words(m)]
    check(not perth, "no WA lead is emailed at 08:30 Perth time")
    first = outbox.sent[0]
    text = words(first)
    check("Pty Ltd" not in text and "|" not in text and "1 Test St" in text and "unsubscribe" in text
          and first["List-Unsubscribe"], "email has the clean name, the footer and the unsubscribe line")
    check(any("your area" in words(m) for m in outbox.sent), "a missing suburb falls back to 'your area'")
    saturday = datetime(2026, 9, 26, 1, 0, tzinfo=timezone.utc)
    check(mailer.send_one(conn, Outbox(), saturday) == "nothing due right now", "nothing is sent on a Saturday")

    print("reading the mailbox")
    a, b, c, d, e, f = outbox.sent[:6]
    check(mailer.handle_inbound(conn, reply_to(a, "Sure, call me tomorrow."), monday) == "reply", "a reply is recognised")
    check(mailer.handle_inbound(conn, reply_to(a, "Sure, call me tomorrow."), monday) == "reply"
          and conn.execute("SELECT COUNT(*) FROM out_events WHERE kind='reply'").fetchone()[0] == 1,
          "reading the same reply twice counts it once")
    snippet = conn.execute("SELECT detail FROM out_events WHERE kind='reply'").fetchone()[0]
    check(snippet == "Sure, call me tomorrow.", "the stored reply is what they typed, without the quoted original")
    check(mailer.handle_inbound(conn, gmail_bounce(b), monday) == "hard bounce", "a Gmail bounce report is a hard bounce")
    check(mailer.handle_inbound(conn, gmail_bounce(c, threaded=False), monday) == "hard bounce",
          "a bounce with no thread headers is matched through the attached original")
    check(mailer.handle_inbound(conn, gmail_bounce(d, status="4.2.2"), monday) == "soft bounce", "a delay is a soft bounce")
    ooo = reply_to(e, "I am away until Monday.", subject="Automatic reply: hello", headers={"Auto-Submitted": "auto-replied"})
    check(mailer.handle_inbound(conn, ooo, monday) == "auto reply", "an out-of-office is not counted as a reply")
    fresh = EmailMessage()
    fresh["From"], fresh["To"], fresh["Subject"], fresh["Message-ID"] = f["To"], ME, "stop", "<fresh-1@their.host>"
    fresh.set_content("Please remove me from your list.")
    check(mailer.handle_inbound(conn, fresh.as_bytes(), monday) == "unsubscribe",
          "an unsubscribe sent as a fresh email is matched by address")
    own = EmailMessage()
    own["From"], own["To"], own["Subject"] = ME, "x@y.com", "hi"
    own.set_content("x")
    check(mailer.handle_inbound(conn, own.as_bytes(), monday) == "ours", "our own sent mail is ignored")
    check(store.is_suppressed(conn, str(b["To"])) and store.is_suppressed(conn, str(f["To"]))
          and not store.is_suppressed(conn, str(d["To"])),
          "hard bounces and unsubscribes join the do-not-contact list, a soft bounce does not")

    print("dead addresses are shared, do-not-contact is not")
    other = Path(tempfile.mkdtemp())
    (other / "project.json").write_text('{"name": "Another client", "country": "AU", "default_tz": "Australia/Sydney"}')
    first_project = store.PROJECT
    store.use(other)
    conn2 = store.connect()
    seed(conn2)
    store.migrate(conn2)
    store.sync_contacts(conn2)
    aud2 = store.audience(conn2, {"trades": ["Plumbers", "Painters & decorators"]})
    dead_reason = "Address is dead (it bounced before, here or in another project)"
    check(aud2["excluded"].get(dead_reason) == 2, "an address that bounced in one project is blocked in a brand new one")
    check(not store.is_suppressed(conn2, str(f["To"])) and str(f["To"]) in {r["email"] for r in aud2["rows"]},
          "an unsubscribe in one project does not carry into another")
    check(set(store.dead_addresses()[0]) == {"email", "why", "added_at"}, "the shared list holds the address and date, not the project")
    conn2.close()
    store.use(first_project)

    print("follow-ups")
    store.suppress(conn, "domain", str(outbox.sent[6]["To"]).split("@")[1], "asked by phone")
    thursday = datetime(2026, 9, 24, 3, 0, tzinfo=timezone.utc)     # 13:00 Sydney, 11:00 Perth
    outbox2 = Outbox()
    drain(conn, outbox2, thursday)
    got = {str(m["To"]) for m in outbox2.sent}
    stopped = {str(m["To"]) for m in (a, b, c, f, outbox.sent[6])}
    check(len(outbox2.sent) == 30 and not (got & stopped), "nobody who replied, bounced, unsubscribed or was suppressed gets another email")
    check(str(d["To"]) in got and str(e["To"]) not in got,
          "a soft bounce still gets its follow-up on time; an out-of-office is left alone for a few days")
    follow = next(m for m in outbox2.sent if str(m["To"]) == str(d["To"]))
    check(follow["In-Reply-To"] == d["Message-ID"] and follow["Subject"] == "Re: " + d["Subject"],
          "the follow-up lands in the same thread as the first email")
    firsts = [m for m in outbox2.sent if not m["In-Reply-To"]]
    order = [bool(m["In-Reply-To"]) for m in outbox2.sent]
    check(order == sorted(order, reverse=True) and firsts, "follow-ups go out before new leads")

    tuesday = datetime(2026, 9, 29, 3, 0, tzinfo=timezone.utc)
    outbox3 = Outbox()
    drain(conn, outbox3, tuesday)
    check(str(e["To"]) in {str(m["To"]) for m in outbox3.sent}, "and then gets the follow-up once they are likely back")

    print("results and safety")
    res = store.results(conn, cid)
    total = {k: sum(x[k] for x in res["arms"]) for k in ("replied", "bounced", "unsubscribed")}
    check(total == {"replied": 1, "bounced": 2, "unsubscribed": 1}, f"results add up ({total})")
    check(res["verdict"].startswith("Too early to call"), "one reply is not called a winner: " + res["verdict"])
    store.set_settings(conn, {"bounce_pause_pct": 4})
    for m in firsts[:3]:
        mailer.handle_inbound(conn, gmail_bounce(m), thursday)
    reason = store.get_settings(conn)["paused_reason"]
    check("bounced" in reason and mailer.send_one(conn, Outbox(), thursday).startswith("paused"),
          "too many bounces stops all sending: " + reason)
    doc2 = store.load_campaign(conn, cid)
    doc2["steps"][0]["versions"][0]["body"] = "sneaky edit"
    store.save_campaign(conn, doc2)
    check(store.load_campaign(conn, cid)["steps"][0]["versions"][0]["body"].startswith("Hi {short_name}"),
          "the emails of a launched campaign cannot be edited")
    fc = store.forecast(store.DEFAULTS, 200, [3, 4, 5, 7])
    check(fc["days_to_first_touch_all"] < fc["days_to_finish"] and fc["days_to_finish"] > 30,
          f"forecast: 200 leads x 5 emails = {fc['days_to_finish']} days at the default ramp")

    failed = [label for ok, label in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
