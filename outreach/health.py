"""health.py: is this inbox set up to be believed?

Three questions, each answered with evidence and a plain next step:
  1. Can we log in, both to send and to read?
  2. Does the domain vouch for the mailbox? (SPF, DKIM, DMARC records, looked up live.)
  3. Does a real email arrive authenticated and with its identity intact? (Send one to itself, read
     it back, and read the receiving server's own verdict in its Authentication-Results header.)

Nothing here guesses. "Could not check" is an allowed answer.
Source: docs/research/2026-09-19-connecting-inboxes.md, 2026-09-19-mass-sending-and-tracking.md
"""
from __future__ import annotations

import email
import email.policy
import imaplib
import re
import smtplib
import time
from email.utils import make_msgid

import mailer
import store

DKIM_SELECTORS = {"google": ["google"], "other": ["default", "selector1", "selector2", "k1", "mail", "dkim"]}
SPF_INCLUDE = {"google": "_spf.google.com"}


def item(name: str, state: str, says: str, fix: str = "") -> dict:
    return {"name": name, "state": state, "says": says, "fix": fix}       # state: ok | warn | bad | unknown


def _txt(resolver, name: str) -> list[str] | None:
    import dns.exception
    import dns.resolver
    for tcp in (False, True):                 # big TXT answers (many records on one name) only fit over TCP
        try:
            return ["".join(p.decode() for p in r.strings) for r in resolver.resolve(name, "TXT", tcp=tcp)]
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return []
        except dns.exception.DNSException:
            continue
    return None


def _spf_reaches(resolver, record: str, want: str, depth: int = 3) -> bool:
    """Does this SPF record allow `want`, directly or through an include? Some registrars (GoDaddy's
    SPF merge, for one) publish a single include that only names the real provider a level deeper."""
    if want in record:
        return True
    if depth <= 0:
        return False
    for host in re.findall(r"include:(\S+)", record, re.I):
        for t in _txt(resolver, host) or []:
            if t.lower().startswith("v=spf1") and _spf_reaches(resolver, t, want, depth - 1):
                return True
    return False


def dns_checks(domain: str, provider: str = "google") -> list[dict]:
    import dns.resolver
    r = dns.resolver.Resolver()
    r.lifetime = 6
    r.use_edns(0, 0, 1232)      # a 2048-bit DKIM key does not fit in a 512-byte answer, and plenty of
    out = []                    # home routers answer no DNS over TCP, so the truncation fallback dies there
    spf = _txt(r, domain)
    records = [t for t in spf or [] if t.lower().startswith("v=spf1")]
    want = SPF_INCLUDE.get(provider)
    if spf is None:
        out.append(item("SPF", "unknown", "Could not look it up just now."))
    elif not records:
        out.append(item("SPF", "bad", f"{domain} has no SPF record.",
                        f"Add a TXT record on {domain}: v=spf1 include:{want or 'your mail provider'} ~all"))
    elif len(records) > 1:
        out.append(item("SPF", "bad", "There are two SPF records. Receivers treat that as none.", "Merge them into one TXT record."))
    elif want and not _spf_reaches(r, records[0], want):
        out.append(item("SPF", "warn", f"The SPF record does not include {want}.", f"Add include:{want} to it."))
    else:
        out.append(item("SPF", "ok", records[0]))

    found = looked = None
    for sel in DKIM_SELECTORS.get(provider, DKIM_SELECTORS["other"]):
        got = _txt(r, f"{sel}._domainkey.{domain}")
        looked = looked or got is not None
        if got and any("p=" in t and len(t) > 60 for t in got):
            found = sel
            break
    if found:
        out.append(item("DKIM", "ok", f"A signing key is published ({found}._domainkey)."))
    elif not looked:
        out.append(item("DKIM", "unknown", "Could not look it up just now."))
    elif provider == "google":
        out.append(item("DKIM", "bad", "No Google signing key is published, so Google signs your mail with its own domain, not yours.",
                        "Google Admin > Apps > Google Workspace > Gmail > Authenticate email: generate the record, add it to DNS, "
                        "then press Start authentication."))
    else:
        out.append(item("DKIM", "unknown", "No key found under the usual names. Your provider may use another name; the test email below settles it."))

    dm = _txt(r, f"_dmarc.{domain}")
    rec = next((t for t in dm or [] if t.lower().startswith("v=dmarc1")), None)
    if dm is None:
        out.append(item("DMARC", "unknown", "Could not look it up just now."))
    elif not rec:
        out.append(item("DMARC", "bad", f"{domain} has no DMARC record.",
                        f"Add a TXT record at _dmarc.{domain}: v=DMARC1; p=none; rua=mailto:postmaster@{domain}"))
    else:
        out.append(item("DMARC", "ok", rec))

    try:
        mx = sorted((x.preference, str(x.exchange)) for x in r.resolve(domain, "MX"))
        if mx[0][1] in (".", ""):
            raise LookupError("null MX: the domain says it accepts no mail")
        out.append(item("Can receive replies", "ok", "Mail for this domain goes to " + mx[0][1].rstrip(".")))
    except Exception:
        out.append(item("Can receive replies", "bad", f"{domain} has no MX record, so replies and bounces cannot arrive.",
                        "Add your mail provider's MX records."))
    return out


def login_checks(mb, password: str) -> list[dict]:
    out = []
    try:
        with smtplib.SMTP_SSL(mb["smtp_host"], int(mb["smtp_port"]), timeout=20) as smtp:
            smtp.login(mb["email"], password)
        out.append(item("Can send", "ok", f"Logged in to {mb['smtp_host']}."))
    except smtplib.SMTPAuthenticationError as e:
        out.append(item("Can send", "bad", "The mail server did not accept this password.", _password_help(mb, e)))
    except Exception as e:
        out.append(item("Can send", "bad", f"Could not reach {mb['smtp_host']}: {e}", "Check the server name and port."))
    try:
        imap = imaplib.IMAP4_SSL(mb["imap_host"], int(mb["imap_port"] or 993), timeout=20)
        imap.login(mb["email"], password)
        folders = mailer.ImapInbox._folders(imap)
        imap.logout()
        out.append(item("Can read replies", "ok", "Reading " + " and ".join(folders) + "."))
    except imaplib.IMAP4.error as e:
        out.append(item("Can read replies", "bad", "The mail server did not accept this password for reading.", _password_help(mb, e)))
    except Exception as e:
        out.append(item("Can read replies", "bad", f"Could not reach {mb['imap_host']}: {e}", "Check the server name."))
    return out


def _password_help(mb, error) -> str:
    if mb["provider"] == "google":
        return ("Use an APP password, not the account password: 16 letters from myaccount.google.com/apppasswords. It needs "
                "2-Step Verification to be on. App passwords stop working whenever the account password changes. If the page says "
                "the setting is not available, your Workspace admin has turned app passwords off.")
    return f"Check the address and password with your mail provider. ({error})"


AUTH_RESULT = re.compile(r"\b(spf|dkim|dmarc)=(\w+)")


def read_auth_results(raw: bytes, our_domain: str) -> list[dict]:
    """The receiving server's own verdict on our email."""
    msg = email.message_from_bytes(raw, policy=email.policy.default)
    header = " ".join(str(h) for h in msg.get_all("Authentication-Results") or [])
    verdicts = dict(AUTH_RESULT.findall(header))
    out = []
    if not verdicts:
        return [item("Arrives authenticated", "unknown", "The receiving server did not add its verdict to the test email.")]
    for key, label in (("spf", "SPF"), ("dkim", "DKIM"), ("dmarc", "DMARC")):
        got = verdicts.get(key)
        out.append(item(f"{label} on a real email", "ok" if got == "pass" else "bad" if got else "unknown",
                        f"The receiving server says {key}={got or 'not reported'}."))
    signer = re.search(r"header\.[di]=@?([\w.-]+)", header)
    if signer and not signer.group(1).lower().endswith(our_domain.lower()):
        out.append(item("Signed as your own domain", "warn",
                        f"The email was signed as {signer.group(1)}, not {our_domain}. It passes today, but your domain earns no reputation of its own.",
                        "Turn on DKIM for your domain (see DKIM above)."))
    return out


def round_trip(mb, password: str, settings: dict, wait_s: int = 45) -> list[dict]:
    """Send one email to the inbox itself and read it back."""
    msg = mailer.build_message(mb, settings, mb["email"], "maps-leads connection test", "This is a test from your own tool. You can delete it.")
    wanted = msg["Message-ID"]
    try:
        mailer.SmtpTransport(mb, password).send(msg)
    except (mailer.NotSent, mailer.Unsure) as e:
        return [item("Test email", "bad", f"Could not send the test email: {e}")]
    reader = mailer.ImapInbox(mb, password)
    imap = reader._login()
    try:
        deadline = time.time() + wait_s
        while time.time() < deadline:
            for folder in reader._folders(imap):
                if imap.select(f'"{folder}"', readonly=True)[0] != "OK":
                    continue
                typ, data = imap.uid("SEARCH", None, "HEADER", "Message-ID", f'"{wanted.strip("<>")}"')
                uids = (data[0] or b"").split()
                if typ == "OK" and uids:
                    raw = imap.uid("FETCH", uids[-1].decode(), "(BODY.PEEK[])")[1][0][1]
                    return ([item("Keeps our message id", "ok", "The mail server kept the id we gave the email, so replies and "
                                  "follow-ups will thread correctly.")] + read_auth_results(raw, mb["email"].rsplit("@", 1)[-1]))
            time.sleep(3)
        return [item("Keeps our message id", "warn", "The test email was sent but could not be found again by its id. Some providers "
                     "(Outlook) replace the id. Replies will be matched by address instead, which still works.")]
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def check_inbox(conn, mb, password: str | None, deep: bool = False) -> dict:
    domain = mb["email"].rsplit("@", 1)[-1]
    items = login_checks(mb, password) if password else [item(
        "Can send", "bad", "No app password has been saved for this inbox yet, so nothing can be sent from it.",
        "Press Edit on this inbox and paste in an app password. The steps for making one are on the Add an inbox screen.")]
    if domain not in store.FREEMAIL:
        items += dns_checks(domain, mb["provider"])
    else:
        items.append(item("Your own domain", "warn", f"{domain} is a free mail address. It works, but cold email from a free address is "
                          "filtered harder and you cannot set SPF, DKIM or DMARC for it.", "Use a mailbox on a domain you own."))
    if deep and password and all(i["state"] == "ok" for i in items[:2]):
        items += round_trip(mb, password, store.get_settings(conn))
    worst = "bad" if any(i["state"] == "bad" for i in items) else "warn" if any(i["state"] == "warn" for i in items) else "ok"
    report = {"worst": worst, "items": items}
    store.update_mailbox(conn, mb["id"], {"health": report, "health_at": store.iso(store.now_utc())})
    return report
