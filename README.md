# maps-leads

Find local businesses on Google Maps, find their email addresses on their own websites, work them on a
leads board, and run careful email campaigns from your own mailbox with reply and bounce tracking.

Everything runs on your machine, from your connection and your mailbox. There is no server, no account,
no API key for Google, no browser automation and no proxy.

```
plumbers in New Zealand  →  Google Maps grid search  →  1 SQLite database per project
                         →  emails + socials from each website
                         →  leads board (table, pipeline, map, charts)
                         →  campaigns from your own inbox, replies and bounces read back
```

If you are an AI agent working in this repo, read [`AGENTS.md`](AGENTS.md) first.

---

## 1. Set up (5 minutes)

You need **macOS** and **[uv](https://docs.astral.sh/uv/)**. Nothing else: every script declares its own
Python dependencies and uv installs them on first run.

```bash
# 1. install uv (skip if `uv --version` already works)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. put the repo at ~/maps-leads (every command in these docs assumes that path)
git clone <this repo> ~/maps-leads

# 3. check everything works: 85 offline checks, takes about a minute, touches nothing real
uv run --script ~/maps-leads/app.py selftest
```

Why macOS: the mailbox password and the optional AI key are kept in the macOS Keychain, and background
sending uses a LaunchAgent. **The scraping, enrichment and database parts are plain Python and run on
Linux and Windows too** (see "Use it without the app" below).

## 2. Use it through the app (easiest)

```bash
uv run --script ~/maps-leads/app.py serve
# open http://127.0.0.1:8770
```

1. **Home → New project.** Give it a name, the country (two letters, e.g. `NZ`, `GB`, `US`) and a
   timezone. A project is one folder in `~/maps-leads-projects/<name>/` holding all of its data.
2. **Find leads.** Type what to search for, one phrase per line (`plumbers`, `emergency plumber`,
   `gas fitter`), pick a country or "near a place + radius". You get a plan card first: how many map
   points, how long it will take. Use **Quick sample** the first time, then **Start**. Jobs keep running
   if you close the app; you can stop and resume.
3. **Find emails.** Once a search is in, press Find emails. It visits each business's website and pulls
   emails and social links (roughly 60 to 70% of businesses with a website have one).
4. **Leads.** The board: table, pipeline stages, map, charts, filters, notes. Filter or select rows and
   press **Email these** to start a draft campaign.
5. **Inboxes.** Add your sending mailbox (see section 4 before you do).
6. **Campaigns.** Write a series of emails, up to four versions of each to compare, preview exactly what
   one real lead will receive, read the pre-flight check, then **Launch to the first 20**, then
   **Send to the rest**.
7. **Replies** and **Do not contact** take care of themselves; replies stop the series for that business.

**Ask tab (optional).** Paste an Anthropic API key on the home screen and you can describe what you want
in words ("find gas fitters around Wellington"). The assistant only *prepares* a search, an email job or a
draft campaign as a card; you press the button. It cannot start, launch or send anything itself, and its
database access is read-only. Everything works without a key.

## 3. Use it without the app (scripts, any OS)

Every script writes into the **current folder**, so make a project folder and work from inside it.

```bash
uv run --script ~/maps-leads/app.py new-project ~/maps-leads-projects/nz-plumbers --name "NZ plumbers" --country NZ --tz Pacific/Auckland
cd ~/maps-leads-projects/nz-plumbers

# A. one quick search (max 120 results, Google's limit for one map view).
#    The place goes in the text itself, as specific as you can: "plumbers in Ponsonby Auckland New Zealand"
uv run --script ~/maps-leads/scrape/gmaps.py search "plumbers in Ponsonby Auckland New Zealand" --max 120 --out data/ponsonby.json

# B. a whole country, city or radius with the self-refining grid
uv run --script ~/maps-leads/scrape/world_grid.py plan --country NZ                     # how many points, how long; sends nothing
uv run --script ~/maps-leads/scrape/world_grid.py run "plumbers" --country NZ \
    --profile "Plumbers" --out-dir data/grid_nz_plumbers
uv run --script ~/maps-leads/scrape/world_grid.py run "plumbers" --country NZ \
    --profile "Plumbers" --out-dir data/grid_nz_plumbers --resume                       # after a stop, crash or block

# C. put the results into the project database (deduped on Google's place_id, scored)
uv run --script ~/maps-leads/leads/pipeline.py ingest data/grid_nz_plumbers/plumbers_full.json
uv run --script ~/maps-leads/leads/pipeline.py summary

# D. find emails and socials on each business's website
uv run --script ~/maps-leads/enrich/enrich_websites.py --limit 50     # pilot
uv run --script ~/maps-leads/enrich/enrich_websites.py                # the rest

# E. get it out
uv run --script ~/maps-leads/leads/pipeline.py export --out exports/nz_plumbers.json
sqlite3 -header -csv leads.db "select name, phone, website, email, suburb, state, rating, review_count from businesses" > exports/nz_plumbers.csv
```

**Always pass `--profile` to the grid.** It is the label a business is filed under ("Plumbers"), and the
email finder only visits businesses that have one. Without it, step D says there is nothing to do.

More detail on how the search works, its limits and how to fix it if Google changes something:
[`scrape/README.md`](scrape/README.md).

## 4. Before you send real email

Read this before connecting a mailbox. Cold email from a fresh setup is the fastest way to burn a domain.

- **Use a separate domain and a Google Workspace mailbox on it**, not your main business address.
- On that domain: turn on **DKIM** in Google Admin, and publish **SPF** and **DMARC** records. The
  Inboxes tab checks each of these live and says exactly what is missing.
- Make a Google **app password** (needs 2-step verification on the account). The Inboxes tab walks you
  through it. It is stored in the Keychain, never in a file.
- Press **Send itself a test**, then use the mailbox like a normal person for **1 to 2 weeks** before the
  first campaign. Start small: 2 versions, about 200 leads.
- The tool already paces itself: a slow start (10 a day, +3 a day, up to 40 per inbox), a few minutes
  between sends, the recipient's business hours, and it stops by itself if bounces climb.
- **Microsoft 365 / Outlook mailboxes are not supported** (Microsoft no longer allows password access for
  reading mail; the Microsoft sign-in is not built). Any provider with SMTP + IMAP and a password works.
- **The law is your job, not the tool's.** Every email names the sender and offers a one-word opt-out,
  and opt-outs are honoured automatically, but check your country's rules (Australia: Spam Act 2003;
  UK/EU: PECR and GDPR; US: CAN-SPAM). Some countries do not allow cold email to businesses at all
  without consent.

Background sending (`app.py schedule on --project <folder>`) checks the inbox and sends at most one email
every two minutes, even when the app is closed. Turn it off with `schedule off`.

## 5. How it is built

**This repo is the product. It never holds data.** Projects live outside it.

| Folder | What it does |
|---|---|
| [`scrape/`](scrape/README.md) | `gmaps.py` Google Maps search over plain HTTP · `world_grid.py` any country, self-refining, resumable · `au_grid.py` the older hand-tuned Australia grid |
| `enrich/` | `enrich_websites.py`: visits each website (homepage, then /contact) for emails, Facebook, Instagram, LinkedIn, Australian ABN |
| `leads/` | `pipeline.py`: one SQLite database per project, deduped and scored · `geo.py`: states and timezones |
| [`board/`](board/README.md) | the leads board, live in the app or exported as one file you can hand to someone |
| [`outreach/`](outreach/README.md) | campaigns, versions, cadences, mailboxes (send + read), bounce classification, results |
| `app/` | the local web app: `server.py`, `runs.py` (jobs that outlive the app), `ask.py` (the optional assistant), the pages |
| `app.py` · `project.py` | the one entry point · what a project is |
| `docs/research/` | four research reports behind the outreach design (deliverability, inbox connection, tracking, email look) |

A project folder (default `~/maps-leads-projects/<name>/`, override with `$MAPS_LEADS_PROJECTS`):

```
project.json          name, country, default timezone
leads.db              every business, plus campaigns, replies, stages, jobs
data/                 raw search runs (resumable)        logs/   exports/
dashboard.spec.json   the board's columns, filters, stages        adapter.py
```

Separate searches for separate purposes are separate projects. The only things shared between projects
live in `~/Library/Application Support/maps-leads/` (`$MAPS_LEADS_HOME`): addresses that hard-bounced
(a dead inbox is dead for everyone; only the address and date are kept) and the AI key.

## 6. Rules the product holds itself to

- **Nothing reaches Google or an inbox without a person pressing a button.** Searches show a plan first.
- **One contact per inbox, not per listing.** A chain with one address on 299 listings gets one email.
  An address that appears on 3+ unrelated websites is treated as a web designer's placeholder and skipped.
- **Do-not-contact and dead addresses are checked before every single send**, not only at launch.
- **Fair comparisons.** Versions are split evenly within each trade and state, launched text is locked,
  and results say "too early to call" until a difference is bigger than chance.
- **A crash cannot send twice.** A send is written down before it is attempted and checked against the
  Sent folder if its result was never seen.
- **A refusal is read for what it means.** A dead address is never written to again; "looks like spam",
  a wrong password or a daily limit pauses the inbox and blames no address.
- **No tracking pixels, no rewritten links, no images.** They get cold email filtered, and half of all
  "opens" are mail programs fetching images on their own.

## 7. Commands

```
uv run --script ~/maps-leads/app.py serve [--port 8770]            # the app
uv run --script ~/maps-leads/app.py selftest                       # every check, offline, on throwaway projects
uv run --script ~/maps-leads/app.py new-project <folder> --name "…" --country CC --tz Area/City
uv run --script ~/maps-leads/app.py sync     --project <folder>    # refresh contacts after new emails were found
uv run --script ~/maps-leads/app.py tick     --project <folder>    # read the mailbox, then send at most one email
uv run --script ~/maps-leads/app.py schedule on|off --project <folder>
```

`--project` can be left out when you run the command from inside the project folder.

## 8. Good to know

- **Always say the country.** For the grid that is `--country NZ` (it pins every point and the language
  to that country). For a single `gmaps.py search`, write the place fully in the query text. Otherwise
  Google answers for the country your internet connection is in and pads thin results with businesses
  from there.
- **Phrasing matters more than the grid.** One keyword finds maybe a third of a category. In one test,
  6 synonyms overlapped the main keyword's results by only 25%. Search 3 to 6 phrasings
  (`plumbers`, `plumbing services`, `emergency plumber`, `gas fitter`) into the same project; duplicates
  are merged on place_id.
- **Pace.** A grid point takes about 12 seconds. New Zealand is about 140 base points per keyword
  (around half an hour), Australia about 770, the UK about 1,200. `plan` tells you before you start.
- **If Google slows you down** (429s, or a run of empty points), the grid backs off, then saves and stops
  with exit code 3. Wait a few hours or change network, then `--resume`. Retrying harder makes it worse.
- **If results suddenly come back empty for queries that clearly have results**, Google changed its
  response shape. `scrape/README.md` → "If this breaks" explains the fix.
- **Australia has extra polish**: state from coordinates when Google gives no address, per-state
  timezones for sending hours, ABN capture. Other countries use the address as given and the project's
  timezone. Adding a country is a few lines in `leads/geo.py`.
- **A known gap in the grid:** a map point is only split into smaller ones when Google returns exactly
  120 results. Busy categories in big cities often return 100 to 119 (duplicates across pages), so those
  points do not split and counts in dense areas come out low. Extra phrasings (above) recover most of it.
- The assistant uses the model named in `app/ask.py` (`MODEL`); change it there if you want another.

## 9. Testing

`app.py selftest` runs a whole campaign with a fake clock, a fake outbox and real-shaped bounce reports,
then the assistant loop with a scripted model. It never touches a real project, the network or a
mailbox. CI (`.github/workflows/selftest.yml`) runs it on every push and also fails if any database or
project data is ever committed. What it cannot cover, and so needs a person once per setup: the real
mailbox login (Inboxes → Check now, Send itself a test) and the first real question to the assistant.

See [`CHANGELOG.md`](CHANGELOG.md) for history and [`LICENSE`](LICENSE) for terms.
