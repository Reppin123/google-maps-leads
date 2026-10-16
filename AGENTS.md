# AGENTS.md: how an AI agent should use this repo

You are working in **maps-leads**: Google Maps business search, website email enrichment, a SQLite leads
database per project, a leads board, and email campaigns from the user's own mailbox. Read `README.md`
for the human view; this file is the operating manual for you.

## Hard rules (never break these)

1. **Never send email, launch a campaign or turn on background sending** (`app.py tick`,
   `app.py schedule on`, the Launch buttons) unless the user has asked for that exact action in this
   conversation. Preparing a draft campaign is fine; sending is the user's decision, every time.
2. **Never commit project data.** No `*.db`, `project.json`, `data/`, `dashboard/`, `exports/` in git.
   `.gitignore` and CI both enforce it; do not work around them. Projects live outside the repo,
   in `~/maps-leads-projects/<name>/`.
3. **Show the plan before a big scrape.** Run `world_grid.py plan` first and tell the user the number
   of points and the estimated time. Anything over about an hour, confirm before you `run`.
4. **Respect Google's pacing.** Do not lower `--pace`, run several grids in parallel from one
   connection, or retry in a loop. If a run exits with **code 3** (blocked), stop and tell the user:
   the fix is time (a few hours) or another network, then `--resume`.
5. **Do not edit the scraper's field map** (`parse_page` / `parse_record` in `scrape/gmaps.py`) unless a
   live search of an obviously busy query returns zero results. That is the only sign Google changed
   the response shape. Then follow `scrape/README.md` → "If this breaks".
6. **Always run `uv run --script ~/maps-leads/app.py selftest` after changing code**, and report the
   count. It is offline and safe. 85/85 is the baseline.

## Running things

- Every script runs with `uv run --script <path>`; dependencies install themselves. Do not create a
  venv or `pip install` anything.
- Scrape, ingest and enrich scripts write into the **current directory**. `cd` into the project folder
  first, or you will create `leads.db` and `data/` in the wrong place.
- Long jobs (a grid run, enrichment of thousands of sites) should run in the background with output
  to a log in the project's `logs/` folder. They are resumable, so an interruption costs nothing.

## The best way to get leads for "<kind of business> in <place>"

1. **Clarify only what you cannot infer:** the country, the area (whole country, a state, a city with a
   radius), and what the leads are for. Do not ask about anything with a sensible default.
2. **Make a project** (one per purpose, never mix two purposes in one database):
   ```bash
   uv run --script ~/maps-leads/app.py new-project ~/maps-leads-projects/<slug> --name "<Name>" --country <CC> --tz <Area/City>
   cd ~/maps-leads-projects/<slug>
   ```
3. **Expand the phrasing.** This matters more than anything else: one keyword typically finds a third
   of a category, and synonyms overlap by as little as 25%. Write 3 to 6 phrasings a customer would
   type (`plumbers`, `plumbing services`, `emergency plumber`, `gas fitter`, `drain cleaning`). Each
   phrasing is its own grid run into the same project; duplicates merge on `place_id`.
4. **Plan, then sample, then run:**
   ```bash
   uv run --script ~/maps-leads/scrape/world_grid.py plan --country NZ            # or --near "Leeds" --country GB --radius-km 30, or --admin1 CA --country US
   uv run --script ~/maps-leads/scrape/world_grid.py run "plumbers" --country NZ --profile "Plumbers" \
       --out-dir data/sample_plumbers --max-points 4 --max-depth 0                 # quick sample: is the phrasing right?
   uv run --script ~/maps-leads/scrape/world_grid.py run "plumbers" --country NZ --profile "Plumbers" \
       --out-dir data/grid_plumbers                                                # the full run, in its own folder
   uv run --script ~/maps-leads/scrape/world_grid.py run "plumbers" --profile "Plumbers" \
       --out-dir data/grid_plumbers --resume                                       # only after a stop, crash or exit 3
   ```
   **Always pass `--profile`** (the category label). The email finder skips businesses without one.
   Use one `--out-dir` per phrasing, and a separate one for a sample: a run's plan is fixed when it
   starts, so `--resume` never grows a sample into a full run, and starting a new run in an existing
   folder wipes that folder's results.
5. **Ingest each finished run:**
   ```bash
   uv run --script ~/maps-leads/leads/pipeline.py ingest data/grid_plumbers/plumbers_full.json
   uv run --script ~/maps-leads/leads/pipeline.py summary
   ```
6. **Find emails**, pilot first:
   ```bash
   uv run --script ~/maps-leads/enrich/enrich_websites.py --limit 50     # check the hit rate (expect 60 to 70% of sites)
   uv run --script ~/maps-leads/enrich/enrich_websites.py                # the rest, about 330 sites a minute
   uv run --script ~/maps-leads/app.py sync                              # builds one contact per inbox for campaigns
   ```
7. **Report honestly:** how many businesses, how many with a website, phone and email, and how many
   were dropped as far-away padding. Say that counts are a floor, not the true total.
8. **Hand over** a CSV (below), or point the user at the board: `app.py serve`, then the project's
   Leads tab.

## Reading the data

One database per project: `leads.db`. Query it read-only with `sqlite3`.

```sql
-- the main table: one row per business (deduped on place_id)
SELECT name, phone, website, email, suburb, state, area, rating, review_count, signal_score
FROM businesses ORDER BY signal_score DESC LIMIT 20;

-- how complete is the list?
SELECT COUNT(*) total,
       SUM(COALESCE(website,'') <> '') with_site,
       SUM(COALESCE(phone,'')   <> '') with_phone,
       SUM(COALESCE(email,'')   <> '') with_email
FROM businesses;

-- enrichment results: ok | partial | no_data | unreachable | NULL (not visited yet)
SELECT enrich_status, COUNT(*) FROM businesses GROUP BY 1;

-- one contact per inbox, used by campaigns (after app.py sync); check_status says why one is excluded
SELECT check_status, COUNT(*) FROM out_contacts GROUP BY 1;
```

CSV for the user:
```bash
sqlite3 -header -csv leads.db "SELECT name, phone, website, email, suburb, state, rating, review_count FROM businesses" > exports/<slug>.csv
```

`signal_score` is a rough lead-quality score (no website, has phone, more reviews score higher; see the
top of `leads/pipeline.py`). Do not present it as anything more than that.

## Email campaigns (only when the user asks)

Campaigns are built in the app (`app.py serve` → Campaigns), not by hand-editing tables. If the user
asks for help:

- Check the Inboxes tab health first: SPF, DKIM, DMARC, an app password, and a successful
  "Send itself a test". A brand-new domain needs 1 to 2 weeks of normal use before cold email.
- Suggest small: 2 versions, about 200 leads, "Launch to the first 20" before the rest.
- Write emails plainly: short, specific to the business's trade and area, no images, no links in the
  first email, a real name and a one-word opt-out (the tool adds it).
- Remind the user once that commercial email law in their country is theirs to follow.
- Microsoft 365 mailboxes are not supported; do not try to make them work with passwords.

## Changing the code

- Read the module's README and the docstring at the top of the file first; they record why things are
  the way they are (measured numbers, traps found the hard way).
- Keep the product generic. Nothing about a specific client, project or person goes in the repo.
- Every script keeps its `# /// script` header with pinned dependencies.
- The assistant in `app/ask.py` must stay unable to start, launch or send anything. Its tools return
  cards the user confirms, and its SQL runs under a SELECT-only SQLite authorizer. Keep it that way.
- After a change: `selftest`, then a quick live sample (`--max-points 4 --max-depth 0`) on a throwaway
  project if you touched scraping. Delete the throwaway project afterwards.

## Where things are

| Need | File |
|---|---|
| One search, the Google field map | `scrape/gmaps.py` |
| Country / city / radius grid, resume, block handling | `scrape/world_grid.py` |
| Database schema, ingest, scoring, export | `leads/pipeline.py` |
| States and timezones (add a country here) | `leads/geo.py` |
| Email and social extraction | `enrich/enrich_websites.py` |
| Contacts, audiences, campaign storage | `outreach/store.py` |
| Sending, reading the mailbox, scheduling | `outreach/mailer.py` |
| Bounce and refusal classification | `outreach/delivery.py` |
| Mailbox health checks (SPF, DKIM, DMARC, MX) | `outreach/health.py` |
| Local web app, background jobs, assistant | `app/server.py`, `app/runs.py`, `app/ask.py` |
| Projects (create, find) | `project.py` |
