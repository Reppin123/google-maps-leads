"""looks.py: how an email looks, and plain advice about how it reads.

Cold email from a personal mailbox should look like a person typed it. So the default look is
"plain": the words exactly as written. It is still sent the way Gmail itself sends mail, as two
matching parts (text and simple HTML), because a lone text part is unusual from a modern mailbox
and an HTML part whose text differs from the text part is what spam filters actually score.

The "light" look allows three things a person might do by hand: **bold**, "- " bullet lists and
[links](https://example.com). Both parts are produced from the same source, so they always match.
No images, no tracking pixels, no rewritten links: this tool has no server to host them and they
are the part of "HTML email" that hurts cold outreach.

Source: docs/research/2026-09-19-email-look-and-feel.md
"""
from __future__ import annotations

import html
import re

BOLD = re.compile(r"\*\*(.+?)\*\*")
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
URL = re.compile(r"https?://\S+")
FONT = "font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#222"


def _text_line(line: str, light: bool) -> str:
    if not light:
        return line
    line = LINK.sub(lambda m: m.group(2) if m.group(1).strip() == m.group(2) else f"{m.group(1)} ({m.group(2)})", line)
    return BOLD.sub(r"\1", line)


def _html_line(line: str, light: bool) -> str:
    out = html.escape(line, quote=False)
    if light:
        out = LINK.sub(lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', out)
        out = BOLD.sub(r"<b>\1</b>", out)
    return out


def _html_block(text: str, light: bool) -> str:
    parts, bullets = [], []
    for line in text.split("\n"):
        if light and line.lstrip().startswith("- "):
            bullets.append(f"<li>{_html_line(line.lstrip()[2:], True)}</li>")
            continue
        if bullets:
            parts.append(f"<ul style=\"margin:0 0 0 18px;padding:0\">{''.join(bullets)}</ul>")
            bullets = []
        parts.append(f"<div>{_html_line(line, light)}</div>" if line.strip() else "<div><br></div>")
    if bullets:
        parts.append(f"<ul style=\"margin:0 0 0 18px;padding:0\">{''.join(bullets)}</ul>")
    return "".join(parts)


def render_parts(body: str, signature: str, footer: str, unsub: str, look: str = "plain") -> tuple[str, str]:
    """(text part, html part). The person's words, then their sign-off, then the small print the law
    asks for: who is writing and how to opt out."""
    light = look == "light"
    blocks = [b.strip("\n") for b in (body.rstrip(), signature.strip()) if b.strip()]
    small = [b.strip() for b in (footer, unsub) if b.strip()]
    text = "\n\n".join(["\n".join(_text_line(ln, light) for ln in b.split("\n")) for b in blocks] + small) + "\n"
    main = "<div><br></div>".join(_html_block(b, light) for b in blocks)
    fine = "<div><br></div>".join(_html_block(b, False) for b in small)
    page = f'<div dir="ltr" style="{FONT}">{main}' + (
        f'<div><br></div><div style="color:#777;font-size:12px">{fine}</div>' if fine else "") + "</div>"
    return text, page


def hints(subject: str, body: str, position: int, same_thread: bool = True) -> list[str]:
    """A few checks a careful friend would make before you hit send. Facts about the draft, no score:
    what is known to matter in cold email is short, specific and one ask."""
    out = []
    words = len(re.findall(r"\b[\w'’]+\b", body))
    subj_words = len(subject.split())
    if position == 1 or not same_thread:
        if subj_words > 9:
            out.append(f"The subject is {subj_words} words. Three to seven reads like a person wrote it.")
        if subject.isupper() and len(subject) > 3:
            out.append("The subject is all capitals.")
        if re.match(r"\s*(re|fwd?):", subject, re.I):
            out.append("A subject that starts with \"Re:\" on a first email is a fake reply. Gmail tells senders not to do this.")
    if words > 160:
        out.append(f"{words} words. Cold emails that get answered are usually under about 125.")
    links = len(URL.findall(body))
    if links > 1:
        out.append(f"{links} links. More than one makes a personal email look like a campaign.")
    if body.count("!") > 2:
        out.append("Several exclamation marks.")
    if position == 1 and body.strip() and "?" not in body:
        out.append("There is no question in this email. One clear question is what people reply to.")
    if re.search(r"<\s*(img|table|div|a)\b", body, re.I):
        out.append("This contains HTML tags. Write plain words; bold, bullets and links are available in the light look.")
    return out
