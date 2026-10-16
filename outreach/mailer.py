"""mailer.py: the sender, the mailbox reader, and the one tick that runs both.

Every inbox is reached directly (SMTP to send, IMAP to read) with a password kept in the
Keychain. Nothing here depends on another app being open.

What keeps it safe:
- The tick reads every inbox BEFORE it sends, so a reply that just arrived stops its follow-up.
  An inbox that cannot be read does not send.
- One email per inbox per tick, then a random wait, inside a daily limit that grows slowly.
- A lead stays on the inbox that wrote to it first. If that inbox breaks, its follow-ups wait
  for it; they are never sent from a stranger's address into the same conversation.
- A send is written down BEFORE it is attempted. If the app dies mid-send, the next tick looks
  in the Sent mail for that exact message before deciding whether to try again. No double sends.
- A refusal is read for what it is about (delivery.py): a dead address is never written to
  again; "your mail looks like spam" or "wrong password" stops the inbox and blames no address.
- Only one tick runs at a time.
"""
from __future__ import annotations

import email
import email.policy
import fcntl
import imaplib
import json
import plistlib
import random
import re
import shutil
import smtplib
import socket
import subprocess
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid, parseaddr
from pathlib import Path
from zoneinfo import ZoneInfo

import delivery
import looks
import store

AUTO_SUBJECT = re.compile(r"^\s*(automatic reply|auto[- ]?reply|out of (the )?office|autoreply)", re.I)
UNSUB = re.compile(r"\b(unsubscribe|remove me|stop emailing|opt[- ]?out|take me off|do not (email|contact))\b", re.I)
QUOTE_START = re.compile(r"^(>|On .{5,120} wrote:|-{2,}\s*Original Message|From: .+@)", re.I)
MSGID = re.compile(r"<[^<>\s]+@[^<>\s]+>")
SOFT_RETRY = [timedelta(hours=1), timedelta(hours=6), timedelta(days=1)]      # then give up on that lead


class NotSent(Exception):
    """The server said no, or we never reached it. The email definitely did not go."""
    def __init__(self, verdict: delivery.Verdict, recipient_level: bool = False):
        super().__init__(verdict.why)
        self.verdict, self.recipient_level = verdict, recipient_level


class Unsure(Exception):
    """The connection died after the email was handed over. It may or may not have gone."""


# ── the app password ────────────────────────────────────────────────────────

def _keychain_service() -> str:
    return f"maps-leads:{store.PROJECT.name}"       # passwords are per project, one per inbox address


def save_password(account: str, password: str) -> None:
    subprocess.run(["security", "add-generic-password", "-U", "-s", _keychain_service(), "-a", account, "-w", password],
                   check=True, capture_output=True)


def load_password(account: str) -> str | None:
    if not account:
        return None
    r = subprocess.run(["security", "find-generic-password", "-s", _keychain_service(), "-a", account, "-w"],
                       capture_output=True, text=True)
    return r.stdout.strip() or None if r.returncode == 0 else None


def forget_password(account: str) -> None:
    subprocess.run(["security", "delete-generic-password", "-s", _keychain_service(), "-a", account], capture_output=True)


# ── transports (the self-test swaps these for in-memory fakes) ──────────────

class SmtpTransport:
    def __init__(self, mb, password: str):
        self.mb, self.password = mb, password

    def send(self, msg: EmailMessage) -> None:
        try:                                          # phase 1: nothing has been handed over yet
            smtp = smtplib.SMTP_SSL(self.mb["smtp_host"], int(self.mb["smtp_port"]), timeout=30)
            smtp.login(self.mb["email"], self.password)
        except smtplib.SMTPResponseException as e:
            raise NotSent(delivery.classify(e.smtp_code, e.smtp_error)) from e
        except (OSError, smtplib.SMTPException) as e:
            raise NotSent(delivery.Verdict(delivery.TEMP, f"Could not reach the mail server: {e}")) from e
        try:                                          # phase 2: a clear "no" is certain, silence is not
            smtp.send_message(msg)
        except smtplib.SMTPRecipientsRefused as e:
            code, text = next(iter(e.recipients.values()))
            raise NotSent(delivery.classify(code, text), recipient_level=True) from e
        except smtplib.SMTPResponseException as e:
            raise NotSent(delivery.classify(e.smtp_code, e.smtp_error)) from e
        except (smtplib.SMTPServerDisconnected, socket.timeout, OSError) as e:
            raise Unsure(str(e)) from e
        finally:
            try:
                smtp.quit()
            except Exception:
                pass


class ImapInbox:
    """Yields (folder, uid, raw bytes) for mail that arrived since the last look. Reads
    All Mail and Spam, because a reply to a cold email can land in either."""

    def __init__(self, mb, password: str):
        self.mb, self.password = mb, password

    def _login(self):
        imap = imaplib.IMAP4_SSL(self.mb["imap_host"], int(self.mb["imap_port"] or 993), timeout=30)
        imap.login(self.mb["email"], self.password)
        return imap

    def fetch_new(self, cursor: dict, since: datetime):
        imap = self._login()
        try:
            for folder in self._folders(imap):
                typ, _ = imap.select(f'"{folder}"', readonly=True)
                if typ != "OK":
                    continue
                validity = (imap.response("UIDVALIDITY")[1] or [b"0"])[0].decode()
                seen = cursor.get(folder, {})
                if seen.get("validity") == validity and seen.get("uid"):
                    typ, data = imap.uid("SEARCH", None, f"UID {int(seen['uid']) + 1}:*")
                else:
                    typ, data = imap.uid("SEARCH", None, "SINCE", since.strftime("%d-%b-%Y"))
                last = int(seen.get("uid") or 0) if seen.get("validity") == validity else 0
                for uid in sorted(int(u) for u in (data[0] or b"").split()):
                    if uid <= last:
                        continue           # "n:*" always returns the newest message, even when it is old
                    typ, parts = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
                    if typ == "OK" and parts and isinstance(parts[0], tuple):
                        yield folder, uid, parts[0][1]
                    last = uid
                cursor[folder] = {"validity": validity, "uid": last}
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def has_message(self, message_id: str) -> bool:
        """Is this exact email in the mailbox (so: did it go)? Used after a send whose ending we did not see."""
        imap = self._login()
        try:
            for folder in self._folders(imap):
                if imap.select(f'"{folder}"', readonly=True)[0] != "OK":
                    continue
                typ, data = imap.uid("SEARCH", None, "HEADER", "Message-ID", f'"{message_id.strip("<>")}"')
                if typ == "OK" and (data[0] or b"").split():
                    return True
            return False
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    @staticmethod
    def _folders(imap) -> list[str]:
        found = {}
        for line in imap.list()[1] or []:
            text = line.decode(errors="replace")
            name = text.rsplit(' "/" ', 1)[-1].strip().strip('"')
            for flag in ("\\All", "\\Junk"):
                if flag in text:
                    found[flag] = name
        return [found.get("\\All", "INBOX")] + ([found["\\Junk"]] if "\\Junk" in found else [])


# ── building one email ──────────────────────────────────────────────────────

def build_message(mb, settings: dict, to_email: str, subject: str, body: str, refs: str = "", look: str = "plain") -> EmailMessage:
    msg = EmailMessage()
    sender = mb["email"]
    local, domain = sender.rsplit("@", 1)
    msg["From"] = formataddr((mb["from_name"] or "", sender))
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=domain)          # our own domain, so the id lines up with the sender
    msg["List-Unsubscribe"] = f"<mailto:{sender}?subject=unsubscribe>"
    if refs:
        msg["In-Reply-To"] = refs.split()[-1]
        msg["References"] = refs
    text, page = looks.render_parts(body, mb["signature"] or "", settings["footer"], settings["unsub_line"], look)
    msg.set_content(text)
    msg.add_alternative(page, subtype="html")               # the same words twice, the way Gmail sends mail
    return msg


def look_for(camp, position: int) -> str:
    return "light" if camp["look"] == "light" and not (position == 1 and camp["first_plain"]) else "plain"


def compose(conn, mb, settings: dict, enr, position: int):
    """The email a lead would get for this step: (message, variant row), or (None, reason)."""
    variant = store.variant_for(conn, enr["campaign_id"], position, enr["arm"])
    if variant is None:
        return None, "this email no longer exists"
    values = store.merge_values(conn, enr["contact_id"])
    subject, miss_s = store.render(variant["subject"], values)
    body, miss_b = store.render(variant["body"], values)
    if miss_s or miss_b:
        return None, "empty merge field: " + ", ".join(sorted(set(miss_s + miss_b)))
    threaded = position > 1 and (variant["same_thread"] or not subject)
    if threaded:
        subject = "Re: " + (enr["first_subject"] or "")
    camp = conn.execute("SELECT look, first_plain FROM out_campaigns WHERE id=?", (enr["campaign_id"],)).fetchone()
    email_to = conn.execute("SELECT email FROM out_contacts WHERE id=?", (enr["contact_id"],)).fetchone()["email"]
    return build_message(mb, settings, email_to, subject, body, enr["refs"] if threaded else "", look_for(camp, position)), variant


# ── sending ─────────────────────────────────────────────────────────────────

def _window_open(camp, tz: str, now: datetime) -> bool:
    local = now.astimezone(ZoneInfo(tz or store.CONF["default_tz"]))
    if str(local.isoweekday()) not in (camp["weekdays"] or "").split(","):
        return False
    return camp["window_start"] <= local.strftime("%H:%M") < camp["window_end"]


def _event(conn, enrollment_id, kind, position, now, detail="", ref=None) -> bool:
    cur = conn.execute("INSERT OR IGNORE INTO out_events(enrollment_id, kind, step_position, at, detail, ref) "
                       "VALUES(?,?,?,?,?,?)", (enrollment_id, kind, position, store.iso(now), detail, ref))
    return cur.rowcount == 1


def _wake(conn, mb, now):
    """An inbox that was resting comes back by itself when its time is up."""
    if mb["status"] == "resting" and mb["resume_at"] and now >= store.parse_iso(mb["resume_at"]):
        store.update_mailbox(conn, mb["id"], {"status": "active", "status_reason": "", "resume_at": None})
        return conn.execute("SELECT * FROM out_mailboxes WHERE id=?", (mb["id"],)).fetchone()
    return mb


def send_one(conn, transport, now: datetime | None = None, rng: random.Random | None = None) -> str:
    """At most one email from EACH inbox that is ready. `transport` is one sender, or a function that
    gives the sender for an inbox."""
    now, rng = now or store.now_utc(), rng or random
    s = store.get_settings(conn)
    if s["paused_reason"]:
        return "paused: " + s["paused_reason"]
    sender_for = transport if callable(transport) else (lambda _mb: transport)
    boxes = [(_wake(conn, mb, now)) for mb in store.mailboxes(conn)]
    if not boxes:
        return "no inbox connected"
    said = []
    ready = sorted(((store.mailbox_capacity(conn, mb, now), mb) for mb in boxes if mb["status"] == "active"),
                   key=lambda pair: -pair[0]["left"])              # the inbox with most room takes new leads first
    for room, mb in ready:
        if mb["next_send_after"] and now < store.parse_iso(mb["next_send_after"]):
            said.append("waiting between sends")
        elif not room["left"]:
            said.append(f"today's limit reached ({room['cap']})")
        else:
            said.append(_send_from(conn, mb, sender_for(mb), s, now, rng))
    if not ready:
        said.append("every inbox is paused, resting or needs attention")
    sent = [x for x in said if x.startswith("sent")]
    if sent:
        return "; ".join(sent)
    for prefix in ("stopped", "today's limit", "waiting", "every inbox"):
        hit = next((x for x in said if x.startswith(prefix)), None)
        if hit:
            return hit
    return said[0]


def _send_from(conn, mb, sender, s: dict, now: datetime, rng) -> str:
    due = conn.execute(
        "SELECT e.*, c.email, c.domain, c.tz, c.place_id, k.window_start, k.window_end, k.weekdays "
        "FROM out_enrollments e JOIN out_campaigns k ON k.id=e.campaign_id JOIN out_contacts c ON c.id=e.contact_id "
        "WHERE k.status='active' AND e.status='active' AND e.next_due <= ? AND (e.mailbox_id = ? OR e.mailbox_id IS NULL) "
        "AND NOT EXISTS (SELECT 1 FROM out_messages m WHERE m.enrollment_id=e.id AND m.state='sending') "
        "ORDER BY e.next_step DESC, e.next_due, e.id LIMIT 500", (store.iso(now), mb["id"])).fetchall()
    for enr in due:                      # follow-ups first: a started conversation outranks a new lead
        if not _window_open(enr, enr["tz"], now):
            continue
        position = enr["next_step"]
        blocked = ("on the do-not-contact list" if store.is_suppressed(conn, enr["email"], enr["place_id"]) else
                   "address is dead: it bounced in another project" if store.is_dead(enr["email"]) else None)
        if blocked:                      # the one gate nothing bypasses
            _stop(conn, enr["id"], position, now, blocked)
            continue
        msg, variant = compose(conn, mb, s, enr, position)
        if msg is None:
            _stop(conn, enr["id"], position, now, variant)
            continue

        # Written down BEFORE it is attempted: a crash from here on can never become a second copy.
        row = conn.execute("INSERT INTO out_messages(enrollment_id, step_position, variant_id, message_id, to_email, subject, "
                           "sent_at, mailbox_id, state) VALUES(?,?,?,?,?,?,?,?,'sending')",
                           (enr["id"], position, variant["id"], msg["Message-ID"], enr["email"], msg["Subject"],
                            store.iso(now), mb["id"])).lastrowid
        conn.commit()
        try:
            sender.send(msg)
        except Unsure as e:
            store.update_mailbox(conn, mb["id"], {"next_send_after": store.iso(now + timedelta(minutes=10))})
            store.set_settings(conn, {"last_error": f"{store.iso(now)} {mb['email']}: connection lost while sending ({e}). "
                                                    "Checking the Sent mail before trying again."})
            return f"unsure whether email {position} to {enr['email']} went; checking before any retry"
        except Exception as e:
            conn.execute("DELETE FROM out_messages WHERE id=?", (row,))
            conn.commit()
            outcome = _refused(conn, mb, enr, position, now, _as_not_sent(e))
            if outcome:
                return outcome
            continue                      # that lead was the problem; the inbox is fine, try the next lead
        _sent(conn, mb, enr, position, row, msg["Message-ID"], msg["Subject"], now, rng)
        return f"sent email {position} to {enr['email']}"
    return "nothing due right now"


def _as_not_sent(e: Exception) -> NotSent:
    if isinstance(e, NotSent):
        return e
    if isinstance(e, smtplib.SMTPRecipientsRefused):
        code, text = next(iter(e.recipients.values()))
        return NotSent(delivery.classify(code, text), recipient_level=True)
    if isinstance(e, smtplib.SMTPResponseException):
        return NotSent(delivery.classify(e.smtp_code, e.smtp_error))
    return NotSent(delivery.Verdict(delivery.TEMP, f"Could not send: {e}"))


def _sent(conn, mb, enr, position, message_row, message_id, subject, now, rng) -> None:
    conn.execute("UPDATE out_messages SET state='sent', sent_at=? WHERE id=?", (store.iso(now), message_row))
    _event(conn, enr["id"], "sent", position, now)
    nxt = conn.execute("SELECT gap_days FROM out_steps WHERE campaign_id=? AND position=?",
                       (enr["campaign_id"], position + 1)).fetchone()
    weekdays = conn.execute("SELECT weekdays FROM out_campaigns WHERE id=?", (enr["campaign_id"],)).fetchone()[0]
    conn.execute(
        "UPDATE out_enrollments SET next_step=?, next_due=?, status=?, refs=?, first_subject=COALESCE(first_subject, ?), "
        "mailbox_id=?, soft_strikes=0 WHERE id=?",
        (position + 1, store.iso(store.after_sending_days(now, nxt["gap_days"], weekdays)) if nxt else None,
         "active" if nxt else "finished", ((enr["refs"] or "") + " " + message_id).strip(), subject, mb["id"], enr["id"]))
    wait = rng.uniform(float(mb["gap_min"]), float(mb["gap_max"]))
    store.update_mailbox(conn, mb["id"], {"next_send_after": store.iso(now + timedelta(minutes=wait))})
    store.set_settings(conn, {"last_error": ""})
    _finish_campaigns(conn)


def _stop(conn, enrollment_id, position, now, why) -> None:
    conn.execute("UPDATE out_enrollments SET status='stopped', next_due=NULL WHERE id=?", (enrollment_id,))
    _event(conn, enrollment_id, "stopped", position, now, why)
    conn.commit()


def _refused(conn, mb, enr, position, now, err: NotSent) -> str | None:
    """Act on a definite "no". Returns a message when the INBOX must stop, None when only that lead was the problem."""
    v = err.verdict
    if v.about_address or (err.recipient_level and v.kind == delivery.TEMP):
        _address_problem(conn, enr["id"], enr["email"], enr["domain"], position, now, v)
        conn.commit()
        return None
    if v.kind == delivery.OURS:
        _stop(conn, enr["id"], position, now, v.why)
        store.set_settings(conn, {"last_error": f"{store.iso(now)} {v.why} ({v.code})"})
        return None
    if v.kind == delivery.BLOCK:
        _event(conn, enr["id"], "blocked", position, now, f"{v.code} {v.why}")
        _stop(conn, enr["id"], position, now, "this email was refused as unwanted; the address was not blamed")
    return _inbox_problem(conn, mb, now, v)


def _address_problem(conn, enrollment_id, address, domain, position, now, v: delivery.Verdict, ref=None) -> str:
    if v.kind in (delivery.HARD, delivery.HARD_DOMAIN):
        if v.kind == delivery.HARD_DOMAIN and domain and domain not in store.FREEMAIL:
            store.suppress(conn, "domain", domain, "domain does not exist")
        _hard_bounce(conn, enrollment_id, address, position, now, f"{v.code} {v.why}", ref)
        return "hard bounce"
    if not _event(conn, enrollment_id, "bounce_soft", position, now, f"{v.code} {v.why}"[:500], ref):
        return "soft bounce"
    enr = conn.execute("SELECT soft_strikes, next_due, status FROM out_enrollments WHERE id=?", (enrollment_id,)).fetchone()
    strikes = (enr["soft_strikes"] or 0) + 1
    if strikes > len(SOFT_RETRY):
        _stop(conn, enrollment_id, position, now, f"gave up after {strikes - 1} temporary failures: {v.why}")
    elif enr["status"] == "active" and enr["next_due"]:
        later = max(store.parse_iso(enr["next_due"]), now + SOFT_RETRY[strikes - 1])
        conn.execute("UPDATE out_enrollments SET soft_strikes=?, next_due=? WHERE id=?", (strikes, store.iso(later), enrollment_id))
    else:
        conn.execute("UPDATE out_enrollments SET soft_strikes=? WHERE id=?", (strikes, enrollment_id))
    return "soft bounce"


def _inbox_problem(conn, mb, now, v: delivery.Verdict) -> str:
    """The inbox, not a lead, is what the server objected to. Rest it or stop it, and say why in plain words."""
    note = f"{v.why} ({v.code})" if v.code else v.why
    if v.kind == delivery.AUTH:
        change = {"status": "broken", "status_reason": note}
    elif v.kind == delivery.DNS:
        change = {"status": "broken", "status_reason": note + " Fix the records, then press Check again."}
    elif v.kind == delivery.QUOTA:
        room = store.mailbox_capacity(conn, mb, now)
        change = {"status": "resting", "status_reason": note, "resume_at": store.iso(now + timedelta(hours=24)),
                  "daily_cap": max(5, min(mb["daily_cap"], room["sent_24h"]) - 5)}
    elif v.kind == delivery.RATE:
        again = mb["slow_until"] and now < store.parse_iso(mb["slow_until"])
        change = ({"status": "broken", "status_reason": note + " This is the second warning in a day, so sending from this inbox "
                   "stays off until you have looked."} if again else
                  {"status": "resting", "status_reason": note, "resume_at": store.iso(now + timedelta(hours=1)),
                   "slow_until": store.iso(now + timedelta(hours=24))})
    elif v.kind == delivery.BLOCK:
        blocks = conn.execute("SELECT COUNT(*) FROM out_events v JOIN out_enrollments e ON e.id=v.enrollment_id "
                              "WHERE v.kind='blocked' AND v.at > ? AND (e.mailbox_id = ? OR e.mailbox_id IS NULL)",
                              (store.iso(now - timedelta(hours=24)), mb["id"])).fetchone()[0]
        if blocks < 2:
            return f"one email was refused as unwanted ({v.code}); carrying on carefully"
        change = {"status": "broken", "status_reason": "Two emails in a day were refused as unwanted. Sending more would hurt "
                  "this inbox. Look at the wording and the volume, then resume."}
    else:                                   # temporary trouble reaching or using the server
        change = {"status": "resting", "status_reason": note, "resume_at": store.iso(now + timedelta(minutes=15))}
    store.update_mailbox(conn, mb["id"], change)
    store.set_settings(conn, {"last_error": f"{store.iso(now)} {mb['email']}: {note}"})
    return f"stopped {mb['email']}: {v.why}"


def _finish_campaigns(conn) -> None:
    conn.execute("UPDATE out_campaigns SET status='done' WHERE status='active' AND NOT EXISTS "
                 "(SELECT 1 FROM out_enrollments e WHERE e.campaign_id=out_campaigns.id AND e.status='active')")
    conn.commit()


def _hard_bounce(conn, enrollment_id, email_addr, position, now, detail, ref=None) -> None:
    if not _event(conn, enrollment_id, "bounce_hard", position, now, detail[:500], ref):
        return
    conn.execute("UPDATE out_enrollments SET status='bounced', next_due=NULL WHERE id=?", (enrollment_id,))
    conn.execute("UPDATE out_contacts SET check_status='bounced' WHERE email=?", (email_addr,))
    store.suppress(conn, "email", email_addr, "hard bounce")
    store.mark_dead(email_addr, detail)
    _bounce_guard(conn, now)


def _bounce_guard(conn, now) -> None:
    """A mailbox that keeps bouncing gets flagged as a spammer. Stop everything and say why. Sized for
    small lists: it looks at the last 50 first emails, not at hundreds."""
    s = store.get_settings(conn)
    recent = [r[0] for r in conn.execute("SELECT enrollment_id FROM out_messages WHERE step_position=1 "
                                         "ORDER BY id DESC LIMIT 50")]
    if len(recent) < 20:
        return
    bounced = conn.execute(f"SELECT COUNT(*) FROM out_enrollments WHERE status='bounced' AND id IN "
                           f"({','.join('?' * len(recent))})", recent).fetchone()[0]
    pct = 100 * bounced / len(recent)
    if bounced >= 3 and pct > float(s["bounce_pause_pct"]):     # one unlucky bounce is not a pattern
        store.set_settings(conn, {"paused_reason": f"{bounced} of the last {len(recent)} new leads bounced "
                                                   f"({pct:.0f}%). Sending stopped to protect the mailbox."})
        _event(conn, None, "auto_pause", None, now, f"bounce rate {pct:.0f}%")


# ── reading the mailbox ─────────────────────────────────────────────────────

def _new_text(msg) -> str:
    """What the person actually typed: the body without the quoted original."""
    part = msg.get_body(preferencelist=("plain", "html"))
    text = part.get_content() if part else ""
    if part is not None and part.get_content_type() == "text/html":
        text = re.sub(r"<(br|/p|/div)[^>]*>", "\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
    lines = []
    for line in text.splitlines():
        if QUOTE_START.match(line.strip()):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _bounce_facts(msg) -> tuple[str, str, list[str]]:
    """(status code, failed recipient, Message-IDs found inside the report)."""
    status, recipient, ids = "", "", []
    for part in msg.walk():
        ctype = part.get_content_type()
        if ctype == "message/delivery-status":
            for block in part.get_payload():
                status = status or str(block.get("Status", ""))
                recipient = recipient or str(block.get("Final-Recipient", "")).split(";")[-1].strip()
        elif ctype in ("message/rfc822", "text/rfc822-headers"):
            ids += MSGID.findall(str(part))
    recipient = recipient or str(msg.get("X-Failed-Recipients", "")).split(",")[0].strip()
    if not status:
        body = _new_text(msg)
        m = re.search(r"\b([45])\.\d{1,3}\.\d{1,3}\b", body) or re.search(r"\b([45])\d\d\b", body)
        status = m.group(0) if m else ""
    return status, recipient.lower(), ids


def handle_inbound(conn, raw: bytes, now: datetime | None = None) -> str:
    now = now or store.now_utc()
    ours = {m["email"].lower() for m in store.mailboxes(conn)}
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    sender = parseaddr(str(msg.get("From", "")))[1].lower()
    if not sender or sender in ours:
        return "ours"
    ref = str(msg.get("Message-ID", "")).strip() or None
    thread_ids = MSGID.findall(str(msg.get("In-Reply-To", "")) + " " + str(msg.get("References", "")))

    is_report = msg.get_content_type() == "multipart/report"
    if is_report or sender.split("@")[0] in ("mailer-daemon", "postmaster"):
        status, recipient, inner = _bounce_facts(msg)
        sent = _find_sent(conn, thread_ids + inner, recipient)
        if not sent:
            return "bounce for something we did not send"
        # Read the report for what it is ABOUT. "Your mail looks like spam" is not a dead address.
        v = delivery.classify(None, f"{status} {_new_text(msg)[:600]}")
        if v.about_address or v.kind == delivery.TEMP:
            domain = sent["to_email"].rsplit("@", 1)[-1]
            out = _address_problem(conn, sent["enrollment_id"], sent["to_email"], domain, sent["step_position"], now, v, ref)
            conn.commit()
            return out
        if _event(conn, sent["enrollment_id"], "blocked", sent["step_position"], now, f"{v.code} {v.why}"[:500], ref):
            _stop(conn, sent["enrollment_id"], sent["step_position"], now, "this email was refused; the address was not blamed")
            mb = conn.execute("SELECT * FROM out_mailboxes WHERE id=?", (sent["mailbox_id"],)).fetchone()
            if mb:
                _inbox_problem(conn, mb, now, v)
        conn.commit()
        return "blocked"

    sent = _find_sent(conn, thread_ids, sender)
    if not sent:
        return "not about a campaign"
    text = _new_text(msg)
    subject = str(msg.get("Subject", ""))
    auto = (str(msg.get("Auto-Submitted", "no")).lower() != "no" or msg.get("X-Autoreply") or msg.get("X-Autorespond")
            or str(msg.get("Precedence", "")).lower() in ("auto_reply", "bulk", "junk") or AUTO_SUBJECT.match(subject))
    if auto:
        if _event(conn, sent["enrollment_id"], "auto_reply", sent["step_position"], now, text[:500], ref):
            # Away is not an answer. The series carries on, but not into an empty office: wait a few days.
            conn.execute("UPDATE out_enrollments SET next_due=MAX(next_due, ?) WHERE id=? AND status='active' AND next_due IS NOT NULL",
                         (store.iso(now + timedelta(days=5)), sent["enrollment_id"]))
        conn.commit()
        return "auto reply"
    wants_out = UNSUB.search(subject) or (UNSUB.search(text) and len(text) < 400)
    kind, status = ("unsubscribe", "unsubscribed") if wants_out else ("reply", "replied")
    if _event(conn, sent["enrollment_id"], kind, sent["step_position"], now, text[:1500], ref):
        conn.execute("UPDATE out_enrollments SET status=?, next_due=NULL WHERE id=?", (status, sent["enrollment_id"]))
        if wants_out:
            store.suppress(conn, "email", sent["to_email"], "asked to unsubscribe")
            if sender != sent["to_email"]:
                store.suppress(conn, "email", sender, "asked to unsubscribe")
        _stop_the_business(conn, sent, now, "asked us to stop" if wants_out else "replied")
        _finish_campaigns(conn)
    conn.commit()
    return kind


def _stop_the_business(conn, sent, now, what: str) -> None:
    """One answer from a business is the business answering. Nobody else there keeps getting the series."""
    domain = sent["to_email"].rsplit("@", 1)[-1]
    if domain in store.FREEMAIL:
        return
    others = conn.execute("SELECT e.id, e.next_step FROM out_enrollments e JOIN out_contacts c ON c.id=e.contact_id "
                          "WHERE c.domain=? AND e.status='active' AND e.id<>?", (domain, sent["enrollment_id"])).fetchall()
    for o in others:
        _stop(conn, o["id"], o["next_step"], now, f"someone else at {domain} {what}")


def _find_sent(conn, message_ids: list[str], address: str):
    """The email of ours this inbound message is about: by thread first, by address second
    (someone who answers in a fresh email instead of hitting reply)."""
    for mid in reversed(message_ids):
        hit = conn.execute("SELECT * FROM out_messages WHERE message_id=?", (mid,)).fetchone()
        if hit:
            return hit
    if address:
        return conn.execute("SELECT * FROM out_messages WHERE to_email=? ORDER BY id DESC LIMIT 1",
                            (address,)).fetchone()
    return None


def watch(conn, inbox, now: datetime | None = None) -> dict:
    """Read every inbox. `inbox` is one reader, or a function giving the reader for an inbox. Returns what
    was seen, and `unread`: the inboxes that could not be read (they must not send this round)."""
    now = now or store.now_utc()
    reader_for = inbox if callable(inbox) else (lambda _mb: inbox)
    seen: dict = {"unread": []}
    for mb in store.mailboxes(conn):
        if mb["status"] == "broken":
            continue
        first = conn.execute("SELECT MIN(sent_at) FROM out_messages WHERE mailbox_id=?", (mb["id"],)).fetchone()[0]
        if not first:
            continue
        cursor = json.loads(mb["imap_cursor"] or "{}")
        try:
            reader = reader_for(mb)
            _reconcile(conn, mb, reader, now)
            for _folder, _uid, raw in reader.fetch_new(cursor, store.parse_iso(first) - timedelta(days=1)):
                kind = handle_inbound(conn, raw, now)
                seen[kind] = seen.get(kind, 0) + 1
            store.update_mailbox(conn, mb["id"], {"imap_cursor": cursor, "last_watch": store.iso(now)})
        except imaplib.IMAP4.error as e:
            seen["unread"].append(mb["id"])
            if re.search(r"AUTHENTICATIONFAILED|Invalid credentials|LOGIN failed", str(e), re.I):
                _inbox_problem(conn, mb, now, delivery.Verdict(delivery.AUTH, "The mailbox password no longer works. Reconnect the inbox."))
            else:
                store.set_settings(conn, {"last_error": f"{store.iso(now)} {mb['email']}: could not read the mailbox: {e}"})
        except OSError as e:
            seen["unread"].append(mb["id"])
            store.set_settings(conn, {"last_error": f"{store.iso(now)} {mb['email']}: could not read the mailbox: {e}"})
    return seen


def _reconcile(conn, mb, reader, now) -> None:
    """Sends whose ending we never saw (a crash, a dropped connection). The Sent mail knows the truth."""
    stuck = conn.execute("SELECT m.*, e.campaign_id, e.refs, e.contact_id FROM out_messages m JOIN out_enrollments e ON e.id=m.enrollment_id "
                         "WHERE m.state='sending' AND m.mailbox_id=?", (mb["id"],)).fetchall()
    for m in stuck:
        age = now - store.parse_iso(m["sent_at"])
        if age < timedelta(minutes=2) or not hasattr(reader, "has_message"):
            continue
        if reader.has_message(m["message_id"]):
            enr = {"id": m["enrollment_id"], "campaign_id": m["campaign_id"], "refs": m["refs"]}
            _sent(conn, mb, enr, m["step_position"], m["id"], m["message_id"], m["subject"], now, random)
        elif age > timedelta(minutes=15):
            conn.execute("DELETE FROM out_messages WHERE id=?", (m["id"],))      # it never went: safe to try again
            conn.commit()


# ── the tick ────────────────────────────────────────────────────────────────

def tick(conn, now: datetime | None = None) -> dict:
    """Read first, then send, and never two ticks at once (the button and the background job can collide)."""
    lock = open(store.PROJECT / ".tick.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return {"send": "another check is already running"}
    try:
        boxes = {mb["id"]: load_password(mb["email"]) for mb in store.mailboxes(conn)}
        if not any(boxes.values()):
            return {"send": "no inbox connected"}
        seen = watch(conn, lambda mb: ImapInbox(mb, boxes[mb["id"]]), now)
        unread = set(seen.pop("unread"))

        def sender_for(mb):
            if mb["id"] in unread or not boxes.get(mb["id"]):
                return _Silent("could not read this inbox, so it does not send this round")
            return SmtpTransport(mb, boxes[mb["id"]])
        return {"watch": seen, "send": send_one(conn, sender_for, now)}
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


class _Silent:
    """Blind to replies means a follow-up could reach someone who already answered."""
    def __init__(self, why):
        self.why = why

    def send(self, _msg):
        raise NotSent(delivery.Verdict(delivery.TEMP, self.why))


# ── background schedule (a LaunchAgent that runs the tick) ──────────────────

def _label() -> str:
    return f"com.maps-leads.tick.{store.PROJECT.name}"


def plist_path() -> Path:
    return Path.home() / "Library/LaunchAgents" / f"{_label()}.plist"


def schedule(turn_on: bool) -> str:
    uid = subprocess.check_output(["id", "-u"], text=True).strip()
    subprocess.run(["launchctl", "bootout", f"gui/{uid}/{_label()}"], capture_output=True)
    if not turn_on:
        plist_path().unlink(missing_ok=True)
        return "Background sending is off."
    app = Path(__file__).resolve().parent.parent / "app.py"
    log = str(store.PROJECT / "logs" / "outreach-tick.log")
    (store.PROJECT / "logs").mkdir(exist_ok=True)
    plist_path().write_bytes(plistlib.dumps({
        "Label": _label(), "StartInterval": 120, "RunAtLoad": True, "StandardOutPath": log, "StandardErrorPath": log,
        "ProgramArguments": [shutil.which("uv") or "/opt/homebrew/bin/uv", "run", "--script", str(app), "tick",
                             "--project", str(store.PROJECT)],
        "EnvironmentVariables": {"PATH": "/opt/homebrew/bin:/usr/bin:/bin"}}))
    subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path())], check=True)
    return "Background sending is on: the mailbox is checked every 2 minutes while this Mac is awake."
