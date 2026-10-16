# Changelog

## 2026-10-16

- First shareable version, with fresh history, under the MIT licence. New README with set-up and step-by-step use (app and plain
  scripts), and `AGENTS.md` (plus `CLAUDE.md`) telling AI agents how to use the repo safely and well.
- `enrich_websites.py --profile-like` now defaults to every business instead of one category.
- Mailbox screen: domain checks (SPF, DKIM, DMARC) fold into one line when they pass; plainer app-password
  steps; an inbox can no longer be saved without a password; SPF found through a nested include counts.

## Unreleased (2026-09-19)

- Several inboxes per project, each with its own pace, signature, status and health check. Leads stay with the
  inbox that wrote first. Connection wizard with live checks (logins, SPF, DKIM, DMARC, MX, send-to-self).
- Sends are recorded before they are attempted and settled against the Sent mail, so a crash cannot double-send.
  One check at a time.
- Server answers and bounce reports are classified: dead address, temporary, policy block, account problem,
  domain records. Policy blocks and account problems stop the inbox and never blame an address.
- Emails go out as matching text and HTML parts. Plain by default, optional light formatting, first email plain.
- Campaign editor: same or new conversation as an explicit choice, gaps in sending days said in words, version
  chips with their own numbers and a reversible rest, real-lead preview (inbox row, desktop, phone, text part,
  step through leads), per-email field usage counted against the real audience, plain writing hints, a
  pre-flight list (blocks, warnings, what will happen), "Launch to the first 20" then "Send to the rest".
- A reply stops the series for the whole business. An out-of-office waits a few days instead of being ignored.
  Emails nobody has received yet stay editable after launch.
- Four research reports in `docs/research/`.
- Self-test: 85 checks.

## 2026-09-18

- Restructured into product modules (`scrape/ enrich/ leads/ board/ outreach/ app/`). Projects now live
  outside the repo, one folder each; the repo holds no data. Removed a generated board file that had been
  committed with data in it.
- One app for every project: home screen, per-project Ask, Leads, Find leads, Campaigns, Inbox, Mailbox,
  Do not contact.
- Leads board served live from the project database; stages and notes saved there; "Email these"; stages
  move forward by themselves as emails go out and replies come in.
- Outreach: series of emails, up to four versions each, fair assignment, recipient-timezone sending window,
  daily limit with a slow start, reply, bounce, out-of-office and unsubscribe handling, results with margins
  of error, automatic stop when bounces climb.
- Find leads: plan first, one phrase after another, jobs survive the app closing, stop and resume, quick sample.
- Assistant: prepares searches, find-emails jobs and draft campaigns as cards to confirm. Cannot run, launch
  or send anything. Read-only database access.
- Dead addresses shared across projects; do-not-contact stays per project.
- Self-test (51 checks) and CI.

## 2026-09-15

- HTTP-only Google Maps search, Australia grid, SQLite pipeline, website email enrichment.
