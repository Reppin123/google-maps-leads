# outreach/ : email campaigns

`outreach/` is a local panel on top of a project's `leads.db`: pick an audience, write a series of
emails with up to four versions of each, schedule it, and watch replies and bounces.
It connects straight to one mailbox (SMTP to send, IMAP to read) with an app password
kept in the macOS Keychain. Its tables are all named `out_*`; scraped rows are only read.

```
uv run --script ~/maps-leads/app.py serve            # the app, http://127.0.0.1:8770
uv run --script ~/maps-leads/app.py sync             # refresh contacts after new enrichment
uv run --script ~/maps-leads/app.py schedule on|off  # read the mailbox + send, every 2 minutes
uv run --script ~/maps-leads/app.py selftest         # whole campaign on a throwaway project
```

Rules it holds itself to: one contact per inbox (not per listing); do-not-contact is checked
before every send; a lead must render in every version before versions are assigned, so the
split stays fair; follow-ups go before new leads; sending stops on its own if bounces climb;
no open-tracking pixels. The mailbox password is kept in the Keychain, one per project.

## How one email goes out

Every 2 minutes the tick (`mailer.tick`) takes a lock, reads every inbox first (so a reply that just arrived
stops its follow-up, and any send whose ending was never seen is settled against the Sent mail), then sends at
most ONE email from each inbox that is ready: the first lead that is due and inside business hours in its own
timezone, follow-ups before new leads, after checking do-not-contact and the shared dead-address list one last
time. An inbox that could not be read does not send that round. Each inbox then waits a random 3 to 9 minutes,
inside its own daily limit that grows from 10 by 3 a day to 40.

## Several inboxes

`out_mailboxes` holds one row per inbox: address, sender name, signature, pace, status (`active`, `paused` by
you, `resting` until a time, `broken` until you look) and its last health report. New leads go to the inbox with
the most room left today. A lead is fixed to the inbox that sent its first email; if that inbox breaks, its
follow-ups wait. There is no warm-up network on purpose: Google shut those down in 2023.

## What a refusal means (`delivery.py`)

| The server says | It is about | What happens |
|---|---|---|
| 5.1.1 no such user, 5.1.2 no such domain | the address | do-not-contact, the shared dead list, counts toward the bounce guard |
| 4.2.2 / 5.2.2 mailbox full, other 4xx for one recipient | the address, for now | retried after 1 hour, 6 hours, a day, then given up; never the dead list |
| 5.7.1 "looks like spam", policy, reputation | our mail | NOT a bounce: the address is not blamed; two in a day stop the inbox |
| 535 bad password | our account | inbox `broken`, asks to reconnect, no retries |
| 5.4.5 daily limit | our account | inbox rests 24 hours and its cap is lowered |
| 4.7.28 / 421 4.7.0 unusual rate | our account | rests an hour, then half speed for a day; a second warning stops it |
| 5.7.26 and friends (SPF, DKIM, DMARC) | our domain | inbox `broken` until the records are fixed |
| anything unrecognised | unknown | treated as temporary; never allowed to mark an address dead |

The same table reads bounce reports that arrive later by email.

## How it looks (`looks.py`) and inbox health (`health.py`)

Two matching parts, text and simple HTML, produced from one source so they cannot disagree. `plain` sends the
words as typed; `light` allows `**bold**`, `- ` bullets and `[links](https://...)`; the first email stays plain
by default. `health.py` logs in both ways, looks up SPF, DKIM, DMARC and MX live, and can send the inbox an
email to itself and read back the receiving server's own verdict and whether our message id survived.

## Files

`store.py` tables and everything that reads or writes them · `mailer.py` send, read, reconcile, schedule ·
`delivery.py` · `looks.py` · `health.py` · `selftest.py` a whole campaign on a throwaway project ·
`selftest_delivery.py` several inboxes, crash recovery, every kind of refusal, how an email looks.

Research behind these choices is in `docs/research/`.
