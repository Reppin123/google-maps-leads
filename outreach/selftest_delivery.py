"""selftest_delivery.py: the parts of sending that only matter when something goes wrong, plus
several inboxes and how an email looks. Throwaway project, fake clock, fake servers, no network."""
from __future__ import annotations

import os
import smtplib
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import delivery
import looks
import mailer
import store
from selftest import Outbox, check, drain, gmail_bounce, reply_to, results, seed, words

MON = datetime(2026, 9, 21, 0, 30, tzinfo=timezone.utc)          # 10:30 Sydney


class Refusing:
    """A mail server that answers one recipient, or everyone, with a given error."""
    def __init__(self, error, only=None):
        self.error, self.only, self.sent, self.calls = error, only, [], 0

    def send(self, msg):
        self.calls += 1
        if self.only is None or str(msg["To"]) == self.only:
            raise self.error
        self.sent.append(msg)


class Sentbox:
    def __init__(self, has):
        self.has = has

    def has_message(self, _mid):
        return self.has

    def fetch_new(self, cursor, since):
        return iter(())


def project(name: str):
    tmp = Path(tempfile.mkdtemp())
    os.environ["MAPS_LEADS_HOME"] = str(tmp / "shared-home")
    (tmp / "project.json").write_text('{"name": "%s", "country": "AU", "default_tz": "Australia/Sydney"}' % name)
    store.use(tmp)
    conn = store.connect()
    seed(conn)
    store.migrate(conn)
    store.sync_contacts(conn)
    store.set_settings(conn, {"footer": "Sender Co, 1 Test St, Sydney NSW"})
    return conn


def inbox(conn, email, **kw):
    return store.add_mailbox(conn, email, {"from_name": "Sam", "signature": "Sam\nSender Co", "gap_min": 0, "gap_max": 0,
                                           "ramp_start": 50, "daily_cap": 50, **kw})


def campaign(conn, **kw):
    doc = {"name": "t", "audience": {"trades": ["Plumbers"], "states": ["NSW", "VIC"]}, "steps": [
        {"versions": [{"subject": "Quick question", "body": "Hi {short_name}, A?"}, {"subject": "Missed calls", "body": "Hi {short_name}, B?"}]},
        {"gap_days": 3, "versions": [{"subject": "", "body": "Following up."}]}], **kw}
    cid = store.save_campaign(conn, doc)
    store.launch(conn, cid, MON, check_domains=None)
    return cid


def main() -> int:
    start = len(results)

    print("what a refusal is about")
    cases = [(550, "5.1.1 The email account that you tried to reach does not exist", delivery.HARD),
             (550, "5.7.1 Our system has detected that this message is likely unsolicited mail", delivery.BLOCK),
             (550, "5.7.26 This mail has been blocked because the sender is unauthenticated. DKIM = did not pass", delivery.DNS),
             (550, "5.4.5 Daily user sending limit exceeded", delivery.QUOTA),
             (421, "4.7.28 Gmail has detected an unusual rate of mail", delivery.RATE),
             (535, "5.7.8 Username and Password not accepted", delivery.AUTH),
             (452, "4.2.2 The recipient's inbox is out of storage space", delivery.FULL),
             (550, "5.1.2 domain not found", delivery.HARD_DOMAIN),
             (550, "5.4.1 Recipient address rejected: Access denied", delivery.HARD),
             (554, "5.9.9 something nobody has seen before", delivery.SOFT),
             (451, "4.3.0 Temporary system problem", delivery.TEMP)]
    wrong = [(c, t[:30], delivery.classify(c, t).kind, want) for c, t, want in cases if delivery.classify(c, t).kind != want]
    check(not wrong, f"eleven real server answers are read correctly {wrong or ''}")
    check(not delivery.classify(554, "5.9.9 mystery").kind.startswith("hard"),
          "an answer we do not recognise never marks an address dead")

    print("several inboxes")
    conn = project("Two inboxes")
    a, b = inbox(conn, "sam@sender-one.com.au"), inbox(conn, "alex@sender-two.com.au")
    cid = campaign(conn)
    box = Outbox()
    drain(conn, box, MON)
    by = dict(conn.execute("SELECT mailbox_id, COUNT(*) FROM out_messages GROUP BY 1").fetchall())
    total = conn.execute("SELECT COUNT(*) FROM out_enrollments").fetchone()[0]
    check(set(by) == {a, b} and abs(by[a] - by[b]) <= 1 and sum(by.values()) == total,
          f"new leads are shared between the inboxes ({by})")
    check({str(m["From"]) for m in box.sent} == {"Sam <sam@sender-one.com.au>", "Sam <alex@sender-two.com.au>"},
          "each email goes out under its own inbox's name and address")
    store.update_mailbox(conn, b, {"status": "broken", "status_reason": "test"})
    thu = MON + timedelta(days=3, hours=2)
    box2 = Outbox()
    drain(conn, box2, thu)
    owners = {r["to_email"]: r["mailbox_id"] for r in conn.execute("SELECT to_email, mailbox_id FROM out_messages WHERE step_position=1")}
    check(box2.sent and all(owners[str(m["To"])] == a for m in box2.sent),
          "a lead stays with the inbox that wrote first: a broken inbox's follow-ups wait, they do not come from a stranger")
    store.update_mailbox(conn, b, {"status": "active"})
    drain(conn, box2, thu)
    check(any(owners[str(m["To"])] == b for m in box2.sent), "and they go out from their own inbox once it is back")
    follow = next(m for m in box2.sent)
    check(follow["In-Reply-To"] and follow["Subject"].startswith("Re: "), "a same-conversation follow-up threads under the first email")

    print("a reply is the business answering")
    conn.execute("INSERT INTO businesses(place_id, name, profile, state, email, website) VALUES('x1','Twin','Plumbers','NSW','bob@lead1.com.au','https://lead1.com.au')")
    store.sync_contacts(conn)
    first = next(m for m in box.sent if str(m["To"]) == "info@lead1.com.au")
    twin = conn.execute("SELECT id FROM out_contacts WHERE email='bob@lead1.com.au'").fetchone()[0]
    conn.execute("INSERT INTO out_enrollments(campaign_id, contact_id, arm, next_step, next_due) VALUES(?,?,0,1,?)", (cid, twin, store.iso(MON)))
    mailer.handle_inbound(conn, reply_to(first, "Yes please call."), MON)
    check(conn.execute("SELECT status FROM out_enrollments WHERE contact_id=?", (twin,)).fetchone()[0] == "stopped",
          "when one person at a business replies, a colleague at the same domain is not emailed")

    print("a crash can never send twice")
    conn = project("Crash")
    inbox(conn, "sam@sender-one.com.au")
    campaign(conn)

    class Dropped:
        def send(self, _m):
            raise mailer.Unsure("connection reset")
    said = mailer.send_one(conn, Dropped(), MON)
    stuck = conn.execute("SELECT * FROM out_messages WHERE state='sending'").fetchall()
    check(said.startswith("unsure") and len(stuck) == 1
          and conn.execute("SELECT next_step FROM out_enrollments WHERE id=?", (stuck[0]["enrollment_id"],)).fetchone()[0] == 1,
          "a send whose ending we never saw is kept as unfinished, and the lead does not move on")
    box = Outbox()
    mailer.send_one(conn, box, MON + timedelta(minutes=11))
    check(box.sent and str(box.sent[0]["To"]) != stuck[0]["to_email"], "that lead is left alone while it is unresolved; others carry on")
    mb = store.mailboxes(conn)[0]
    mailer._reconcile(conn, mb, Sentbox(True), MON + timedelta(minutes=12))
    row = conn.execute("SELECT state FROM out_messages WHERE id=?", (stuck[0]["id"],)).fetchone()
    check(row["state"] == "sent" and conn.execute("SELECT next_step FROM out_enrollments WHERE id=?", (stuck[0]["enrollment_id"],)).fetchone()[0] == 2
          and conn.execute("SELECT COUNT(*) FROM out_messages WHERE to_email=?", (stuck[0]["to_email"],)).fetchone()[0] == 1,
          "if the Sent mail has it, it counts as sent, once")
    mailer.send_one(conn, Dropped(), MON + timedelta(minutes=30))
    again = conn.execute("SELECT * FROM out_messages WHERE state='sending'").fetchone()
    mailer._reconcile(conn, mb, Sentbox(False), MON + timedelta(minutes=50))
    check(not conn.execute("SELECT 1 FROM out_messages WHERE id=?", (again["id"],)).fetchone(),
          "if the Sent mail does not have it after 15 minutes, it is cleared so it can be tried again")

    print("refusals")
    conn = project("Refusals")
    mid = inbox(conn, "sam@sender-one.com.au")
    campaign(conn)
    victim = conn.execute("SELECT c.email FROM out_enrollments e JOIN out_contacts c ON c.id=e.contact_id ORDER BY e.id LIMIT 1").fetchone()[0]
    gone = Refusing(smtplib.SMTPRecipientsRefused({victim: (550, b"5.1.1 does not exist")}), only=victim)
    mailer.send_one(conn, gone, MON)
    check(store.is_dead(victim) and store.is_suppressed(conn, victim) and len(gone.sent) == 1,
          "\"no such address\" marks it dead everywhere, and the inbox simply moves to the next lead")
    spam = Refusing(smtplib.SMTPDataError(550, b"5.7.1 message is likely unsolicited mail"))
    out1 = mailer.send_one(conn, spam, MON + timedelta(minutes=1))
    blamed = conn.execute("SELECT to_email FROM out_messages").fetchall()
    target = conn.execute("SELECT c.email FROM out_events v JOIN out_enrollments e ON e.id=v.enrollment_id JOIN out_contacts c "
                          "ON c.id=e.contact_id WHERE v.kind='blocked'").fetchone()[0]
    check("carrying on" in out1 and not store.is_dead(target) and not store.is_suppressed(conn, target),
          "\"this looks like spam\" is not a bounce: the address is not blamed and not added to any list")
    out2 = mailer.send_one(conn, spam, MON + timedelta(minutes=2))
    mb = store.mailboxes(conn)[0]
    check(mb["status"] == "broken" and "refused as unwanted" in mb["status_reason"] and out2.startswith("stopped"),
          "two of those in a day stop the inbox until a person has looked")
    calls = spam.calls
    mailer.send_one(conn, spam, MON + timedelta(minutes=5))
    check(spam.calls == calls, "a stopped inbox does not keep trying")

    for label, error, status, extra in [
            ("a wrong password stops the inbox and asks to reconnect", smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted"), "broken", None),
            ("the provider's daily limit rests the inbox for a day and lowers its cap", smtplib.SMTPDataError(550, b"5.4.5 Daily user sending limit exceeded"), "resting", "cap"),
            ("\"unusual rate\" rests it for an hour, then runs it at half speed", smtplib.SMTPDataError(421, b"4.7.28 unusual rate of mail"), "resting", "slow")]:
        conn = project("Account")
        mid = inbox(conn, "sam@sender-one.com.au")
        campaign(conn)
        mailer.send_one(conn, Refusing(error), MON)
        mb = store.mailboxes(conn)[0]
        ok = mb["status"] == status and not conn.execute("SELECT COUNT(*) FROM out_messages").fetchone()[0] \
            and not conn.execute("SELECT COUNT(*) FROM out_suppressed").fetchone()[0]
        if extra == "cap":
            ok = ok and mb["daily_cap"] < 50 and mb["resume_at"] == store.iso(MON + timedelta(hours=24))
        if extra == "slow":
            ok = ok and store.mailbox_capacity(conn, mb, MON + timedelta(hours=2))["cap"] == 25
            box = Outbox()
            mailer.send_one(conn, box, MON + timedelta(hours=1, minutes=1))
            ok = ok and len(box.sent) == 1 and store.mailboxes(conn)[0]["status"] == "active"
        check(ok, label + ", and no lead is blamed")

    conn = project("Soft")
    inbox(conn, "sam@sender-one.com.au")
    campaign(conn)
    victim = conn.execute("SELECT c.email FROM out_enrollments e JOIN out_contacts c ON c.id=e.contact_id ORDER BY e.id LIMIT 1").fetchone()[0]
    full = Refusing(smtplib.SMTPRecipientsRefused({victim: (452, b"4.2.2 mailbox full")}), only=victim)
    t = MON
    for _ in range(4):
        drain(conn, full, t)                 # the others go out; the full mailbox is tried each time it comes due
        due = conn.execute("SELECT e.next_due FROM out_enrollments e JOIN out_contacts c ON c.id=e.contact_id WHERE c.email=?", (victim,)).fetchone()[0]
        t = store.parse_iso(due) + timedelta(minutes=1) if due else t
        while t.isoweekday() > 5 or not (0 <= t.hour < 6):
            t += timedelta(hours=1)
    st = conn.execute("SELECT e.status FROM out_enrollments e JOIN out_contacts c ON c.id=e.contact_id WHERE c.email=?", (victim,)).fetchone()[0]
    check(st == "stopped" and not store.is_dead(victim) and not store.is_suppressed(conn, victim),
          "a full mailbox is retried later a few times, then given up on, and never marked dead")
    earlier = full.sent[0]
    report = gmail_bounce(earlier, status="5.7.1").replace(b"no such user", b"blocked: message looks like spam")
    check(mailer.handle_inbound(conn, report, t) == "blocked" and not store.is_dead(str(earlier["To"])),
          "a bounce REPORT that says \"blocked as spam\" is read the same way: not a dead address")

    print("how an email looks")
    text, page = looks.render_parts("Hi **Bob**,\n\nTwo things:\n- faster quotes\n- fewer missed calls\n\nSee [our page](https://example.com/x).",
                                    "Sam\nSender Co", "Sender Co, 1 Test St", "Reply unsubscribe to stop.", "light")
    check("<b>Bob</b>" in page and "<li>faster quotes</li>" in page and '<a href="https://example.com/x">our page</a>' in page
          and "**" not in text and "our page (https://example.com/x)" in text and "- faster quotes" in text,
          "light formatting: bold, bullets and links in the HTML part, clean readable words in the text part")
    import html as _h, re as _re
    flat = lambda t: _re.sub(r"\s+", " ", t).strip()
    seen = flat(_h.unescape(_re.sub(r"<[^>]+>", " ", page.replace("</li>", "\n"))))
    check(all(w in seen for w in ("Bob", "faster quotes", "Sender Co", "unsubscribe")) and "<script" not in page,
          "both parts say the same thing, which is what spam filters actually check")
    plain_text, plain_page = looks.render_parts("Hi **Bob** <b>x</b>", "", "", "", "plain")
    check("**Bob**" in plain_text and "&lt;b&gt;" in plain_page and "<b>" not in plain_page, "the plain look sends your words exactly as typed")
    conn = project("Looks")
    inbox(conn, "sam@sender-one.com.au")
    cid = campaign(conn, look="light", steps=[
        {"versions": [{"subject": "Quick question", "body": "Hi **{short_name}**?"}]},
        {"gap_days": 2, "same_thread": 0, "versions": [{"subject": "A different idea", "body": "- one\n- two"}]}])
    box = Outbox()
    mailer.send_one(conn, box, MON)
    m = box.sent[0]
    check(m.get_content_type() == "multipart/alternative" and "<b>" not in m.get_body(("html",)).get_content()
          and m["Message-ID"].endswith("@sender-one.com.au>") and m["List-Unsubscribe"],
          "sent as two matching parts like Gmail does, first email kept plain, id on our own domain, opt-out header set")
    conn.execute("UPDATE out_enrollments SET next_due=? WHERE next_step=2", (store.iso(MON),))
    box = Outbox()
    mailer.send_one(conn, box, MON + timedelta(minutes=1))
    f = box.sent[0]
    check(f["Subject"] == "A different idea" and not f["In-Reply-To"] and "<li>one</li>" in f.get_body(("html",)).get_content(),
          "a follow-up set to \"new conversation\" gets its own subject and no thread, and the light look applies to it")

    print("versions and editing after launch")
    conn = project("Versions")
    inbox(conn, "sam@sender-one.com.au")
    cid = campaign(conn)
    doc = store.load_campaign(conn, cid)
    doc["steps"][0]["versions"][1]["paused"] = 1
    doc["steps"][1]["versions"][0]["body"] = "A better follow-up."
    store.save_campaign(conn, doc)
    box = Outbox()
    drain(conn, box, MON)
    check(box.sent and all("A?" in words(m) for m in box.sent), "resting version B sends its leads version A instead")
    doc = store.load_campaign(conn, cid)
    doc["steps"][0]["versions"][1]["paused"] = 0
    doc["steps"][0]["versions"][0]["body"] = "sneaky"
    store.save_campaign(conn, doc)
    after = store.load_campaign(conn, cid)
    check(after["steps"][0]["versions"][1]["paused"] == 0 and after["steps"][0]["versions"][0]["body"].startswith("Hi {short_name}")
          and after["steps"][1]["versions"][0]["body"] == "A better follow-up.",
          "resting is reversible; an email nobody has received yet can still be edited; one that has gone out cannot")
    check(store.after_sending_days(datetime(2026, 9, 25, 1, 0, tzinfo=timezone.utc), 3, "1,2,3,4,5").strftime("%a") == "Wed",
          "a 3 day gap from a Friday lands on Wednesday: gaps count sending days")

    print("before it goes, and a careful start")
    conn = project("Preflight")
    draft = {"name": "bad", "audience": {"trades": ["Plumbers"]}, "steps": [
        {"versions": [{"subject": "Re: your quote", "body": "Hi {short_name} in {suburb}. " + "We are great. " * 60 + " https://a.example https://b.example"}]},
        {"gap_days": 2, "same_thread": 0, "versions": [{"subject": "", "body": "Again."}]}]}
    cid = store.save_campaign(conn, draft)
    pf = store.preflight(conn, store.load_campaign(conn, cid), store.get_settings(conn), False)
    texts = " | ".join(o["level"] + ":" + o["text"] for o in pf)
    check(all(w in texts for w in ("block:Connect the mailbox first", "needs a subject line", "fake reply", "words.", "2 links", "have no suburb"))
          and pf[0]["level"] == "block" and pf[-1]["level"] == "info",
          "the pre-flight names what blocks a launch, what is only a warning, and what will simply happen, worst first")
    usage = store.field_usage(conn, store.load_campaign(conn, cid))[0]
    check({f["field"]: f["empty"] for f in usage["fields"]}.get("suburb", 0) > 0 and usage["leads"] > 0,
          "each email says how many real leads have nothing for a field it uses")
    inbox(conn, "sam@sender-one.com.au")
    good = campaign(conn, name="careful")
    conn.execute("DELETE FROM out_enrollments WHERE campaign_id=?", (good,))
    conn.execute("UPDATE out_campaigns SET status='draft' WHERE id=?", (good,))
    one = store.launch(conn, good, MON, check_domains=None, first=6)
    two = store.launch(conn, good, MON, check_domains=None)
    arms = [r[0] for r in conn.execute("SELECT COUNT(*) FROM out_enrollments WHERE campaign_id=? GROUP BY arm", (good,))]
    check(one["enrolled"] == 6 and one["still_waiting"] == two["enrolled"] > 0 and two["still_waiting"] == 0 and abs(arms[0] - arms[1]) <= 1,
          f"launch to the first 6, then the rest: nobody twice, versions still even ({arms})")

    print("one check at a time")
    import fcntl
    held = open(store.PROJECT / ".tick.lock", "w")
    fcntl.flock(held, fcntl.LOCK_EX)
    check(mailer.tick(conn) == {"send": "another check is already running"}, "a second check while one is running does nothing")
    fcntl.flock(held, fcntl.LOCK_UN)

    return 1 if [1 for ok, _ in results[start:] if not ok] else 0


if __name__ == "__main__":
    raise SystemExit(main())
