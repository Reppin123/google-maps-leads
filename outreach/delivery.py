"""delivery.py: what a mail server's answer means, and what to do about it.

One place for the rule, used both when the sending server answers straight away and when a
bounce report arrives later. The distinction that matters most: a refusal can be about the
ADDRESS (it does not exist: never write again), about the MESSAGE or our REPUTATION (the
address may be fine: stop and look, never blame the address), or about OUR ACCOUNT (wrong
password, daily quota: stop sending, nothing to do with any recipient).

Source for the table: docs/research/2026-09-19-mass-sending-and-tracking.md section 6.1.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# What happened                         who it is about   what the sender does
HARD = "hard"            # address       no such mailbox: do-not-contact + the shared dead list
HARD_DOMAIN = "hard_domain"  # domain    no such domain: every address there
SOFT = "soft"            # address       temporary: try again later, give up after a few strikes, never the dead list
FULL = "full"            # address       mailbox full: as soft
BLOCK = "block"          # our mail      refused as unwanted: NOT a bounce; two of these stop the inbox
AUTH = "auth"            # our account   password no longer works: stop, ask to reconnect, do not retry
QUOTA = "quota"          # our account   the provider's daily limit: rest 24 hours, lower the cap
RATE = "rate"            # our account   "unusual rate": rest an hour, then half speed for a day
DNS = "dns"              # our domain    SPF, DKIM or DMARC failed: stop until the records are fixed
TEMP = "temp"            # their server  temporary system trouble: back off and retry the same email
OURS = "ours"            # our message   malformed or too large: stop this email, tell the person

ENHANCED = re.compile(r"\b([245])\.(\d{1,3})\.(\d{1,3})\b")
UNWANTED = re.compile(r"spam|blocked|block list|blacklist|policy|reputation|unsolicited|not accepted|rejected for|junk", re.I)
GONE = re.compile(r"disabled|inactive|deactivated|no longer|does not exist|unknown user|no such user|user unknown|"
                  r"address rejected|recipient not found|invalid recipient|access denied", re.I)


@dataclass(frozen=True)
class Verdict:
    kind: str
    why: str                 # plain words for the person
    code: str = ""

    @property
    def about_address(self) -> bool:
        return self.kind in (HARD, HARD_DOMAIN, SOFT, FULL)

    @property
    def stops_inbox(self) -> bool:
        return self.kind in (AUTH, QUOTA, RATE, DNS, BLOCK)


def classify(code: int | None, text: str) -> Verdict:
    """`code` is the three-digit reply (None when only a bounce report's text is known)."""
    text = text if isinstance(text, str) else (text or b"").decode(errors="replace")
    m = ENHANCED.search(text)
    enh = m.group(0) if m else ""
    cls, subj, det = (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0, 0, 0)
    code = code or (500 if cls == 5 else 400 if cls == 4 else 0)
    tag = f"{code} {enh}".strip()

    if code in (535, 534) or enh in ("5.7.8", "5.7.80", "5.7.9", "5.7.14"):
        return Verdict(AUTH, "The mailbox password no longer works. Reconnect the inbox.", tag)
    if code == 454:
        return Verdict(RATE, "The mail server is refusing logins for now. Resting for a while.", tag)
    if enh in ("5.7.26", "5.7.27", "5.7.30", "5.7.515", "4.7.27", "4.7.30", "4.7.31") or re.search(r"\b(SPF|DKIM|DMARC)\b", text):
        return Verdict(DNS, "The receiving server says your domain's SPF, DKIM or DMARC record is missing or failing.", tag)
    if enh == "5.4.5" or re.search(r"daily (user )?sending (quota|limit)", text, re.I):
        return Verdict(QUOTA, "This mailbox hit its provider's daily sending limit. Resting for 24 hours.", tag)
    if enh in ("4.7.28", "4.7.0") or (code == 421 and subj == 7):
        return Verdict(RATE, "The mail server says mail is going out too fast or looks unusual. Resting, then half speed.", tag)
    if enh in ("5.1.2", "5.4.4", "5.1.8") or re.search(r"domain (name )?(not found|does not exist)|no mx|nxdomain", text, re.I):
        return Verdict(HARD_DOMAIN, "That domain does not exist or accepts no mail.", tag)
    if enh in ("5.1.1", "5.1.10", "5.1.0", "5.1.3", "5.1.6"):
        return Verdict(HARD, "That address does not exist.", tag)
    if enh in ("4.2.2", "5.2.2") or re.search(r"mailbox (is )?full|over quota|out of storage", text, re.I):
        return Verdict(FULL, "Their mailbox is full.", tag)
    if enh in ("5.2.3", "5.3.4") or enh.startswith("5.6."):
        return Verdict(OURS, "The email itself was refused as too large or malformed.", tag)
    if cls == 5 and subj == 7 or (cls == 5 and UNWANTED.search(text)):
        return Verdict(BLOCK, "The receiving server refused this email as unwanted. The address may be fine; "
                              "the wording, the volume or the domain's reputation is the problem.", tag)
    if enh == "5.4.1" and GONE.search(text):                 # Microsoft's way of saying no such address
        return Verdict(HARD, "That address does not exist.", tag)
    if enh == "5.2.1":
        return Verdict(HARD if GONE.search(text) else SOFT, "That mailbox is disabled." if GONE.search(text)
                       else "That mailbox is not taking mail right now.", tag)
    if cls == 5 and subj == 4:
        return Verdict(SOFT, "Their mail server could not be reached after days of trying.", tag)
    if cls == 4 or 400 <= code < 500:
        return Verdict(TEMP if subj in (3, 4, 0) and not enh.startswith("4.2") else SOFT,
                       "A temporary problem on the receiving side.", tag)
    if code == 550 and not enh and GONE.search(text):
        return Verdict(HARD, "That address does not exist.", tag)
    # A 5xx we do not understand is never allowed to poison the shared dead list.
    return Verdict(SOFT, "The receiving server refused this email for a reason we do not recognise.", tag)
