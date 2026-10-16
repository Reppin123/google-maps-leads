# scrape/ : find businesses on Google Maps

`gmaps.py` is the core: an HTTP-only search against the endpoint Google Maps itself uses. No browser, no
API key, no login. `world_grid.py` covers any country with a population-weighted grid that splits busy
areas by itself. `au_grid.py` is the original hand-tuned Australia grid, kept because older runs used it.

All three write into the current folder, so run them from inside a project folder. Inside the app, the
**Find leads** tab does the same thing with a plan you confirm first (`app/runs.py`).

## Why this over Apify / a Playwright-based scraper

The official Google Places API caps out at 120 results per area and costs
per call. Apify's `compass/crawler-google-places` actor gets around that but
charges $1.50–4 per 1,000 places and runs a full browser under the hood.
Open-source alternatives (`gosom/google-maps-scraper`, `noworneverev/
google-maps-scraper`) also wrap Playwright — ~120 places/minute, needs a
proxy pool at scale, downloads browser binaries, heavier to run in the
background.

This hits the same endpoint directly with `requests`. No browser process,
no proxy needed at our volumes, sub-second per page, runs anywhere Python
runs (including scheduled/background jobs with no display).

## What you get per business

Name, full address, lat/lng, category list, phone, website, Google rating,
review count, `place_id` + `cid` (both usable to build a direct Maps link),
a thumbnail photo URL, and raw opening-hours data.

## How it works

1. Query Google's map search endpoint with a plain text query (e.g.
   `"electricians in Fitzroy VIC"`) — the text itself does the location
   matching, so no separate geocoding step is needed.
2. Response is JSON prefixed with `)]}'` (Google's anti-hijacking guard) —
   strip the prefix, `json.loads` the rest.
3. Each business is a deeply nested array. Field positions were mapped by
   hand against a captured response (see the docstring at the top of
   `gmaps.py` for the exact index map).
4. Paginate by incrementing the `8i` offset in the `pb` parameter in steps
   of 20 (Google's per-page max) until a page comes back empty/short or
   fully duplicate — that's the natural end of results for that query.

## Usage

```bash
# one query
uv run --script ~/maps-leads/scrape/gmaps.py search "electricians in Fitzroy VIC" --max 120 --out data/electricians_fitzroy.json

# batch from a plain text file, one query per line
uv run --script ~/maps-leads/scrape/gmaps.py batch data/queries.txt --out-dir data/batch_run --max 60

# batch from a JSON list of {"profile","suburb","state","tier"} — builds
# "<profile> in <suburb> <state>" queries automatically (this is the shape
# to use for a list of target trades by suburb)
uv run --script ~/maps-leads/scrape/gmaps.py batch-profiles data/targets.json --out-dir data/batch_run --max 60
```

Only dependency is `requests`, pinned via the `uv` inline script header —
run with `uv run --script` and it self-installs.

## Any country: `world_grid.py`

`au_grid.py` is a hand-typed list of Australian cities. `world_grid.py` replaces the
hand-typing with GeoNames (`data/geonames/cities500.txt`, auto-downloaded, every
populated place on Earth with 500+ people) and works for any country, state, city
radius or bounding box:

```bash
uv run --script ~/maps-leads/scrape/world_grid.py plan --country NZ                       # seeds, points, time estimate; no requests
uv run --script ~/maps-leads/scrape/world_grid.py plan --country US --admin1 CA
uv run --script ~/maps-leads/scrape/world_grid.py plan --near Toronto --country CA --radius-km 40
uv run --script ~/maps-leads/scrape/world_grid.py seeds --country GB                      # the places it picked and what it absorbed
uv run --script ~/maps-leads/scrape/world_grid.py run "plumbers" --country NZ --out-dir data/grid_nz_plumbers
uv run --script ~/maps-leads/scrape/world_grid.py run "plumbers" --out-dir data/grid_nz_plumbers --resume
uv run --script ~/maps-leads/leads/pipeline.py ingest data/grid_nz_plumbers/plumbers_full.json
```

How it decides where to look:

- **Coverage from population.** Each place gets a lattice of half-width
  `16 * sqrt(pop / 1M)` km (Sydney 38 km, Adelaide 19, Hobart 8, a 100k town one
  point). This reproduces the hand-tuned AU grid: every one of its 48 centres is
  within 7 km of an auto point, and the auto grid also found 166 populated places the
  hand grid skipped (Mandurah 107k, Maitland 90k, Gladstone, Albany, …).
- **Suburbs are absorbed.** GeoNames lists Logan City, Point Cook, Tuggeranong etc. as
  their own places; anything inside a bigger place's lattice is folded into it.
- **Self-refining.** Measured on 4,931 AU points: 36% of all points and ~50% of metro
  points returned Google's 120 cap, i.e. the fixed 6 km grid undercounted every dense
  suburb. Any capped point now splits into 4 children at half the spacing (6 → 3 →
  1.5 km, `--max-depth`), and a child that is still capped but adds <15% new
  businesses stops splitting (that is overlap, not density).
- **Bleed filter per point.** Results farther than `--max-dist-km` (250) from their
  own viewport are dropped. Replaces the AU bounding box; works across borders.
- **Resumable.** `plan.json` + `state.json` + append-only `results.jsonl` in the run
  dir. Ctrl-C, crash, or a 429/503 block (backs off 60/120/240 s, then saves and exits
  3) loses nothing. A streak of 10 empty points is treated as a block too, because
  Google's captcha page parses as "no results".
- **Rows carry provenance.** `_point_lat/_point_lng/_point_depth/_point_dist_km`,
  plus `_area` (the GeoNames place the point belongs to, e.g. "Auckland") and `_cc`.
  `pipeline.py` stores `area`, `cc` and `country` (last segment of the address) and
  parses suburb/state generically outside AU. `_area` exists for every row, including
  the 40–60% of service-area businesses Google returns with no address at all.

Scale, for planning (base points at 6 km, before refinement): NZ 137 · Toronto 40 km
86 · California 619 · AU 766 · GB 1,214 · India 7,944 · whole world at 100k+ towns
50,130. At the default pace a country-sized run is hours per keyword; the globe is
weeks. `plan` prints the estimate before anything is requested.

Verified live 2026-09-18: Auckland "plumbers", 10 points, 105 unique businesses,
addresses localised to New Zealand, refinement and resume exercised, ingested with
area/country filled.

## Pacing / staying under the radar

Batch mode paces 1.5–4s between requests with a rotating User-Agent, no
cookies or auth needed since the endpoint is public. At the volumes this
project needs (dozens to low hundreds of queries), this comfortably avoids
rate limiting. If a queue gets into the thousands of queries, add proxy
rotation to `fetch_page()` before running it — not needed yet.

## If this breaks

Google can change the internal response shape without notice, which is the
one real fragility of hitting an undocumented endpoint directly. If
`parse_page()` starts returning empty lists on a query that clearly has
results, the fix is: capture a fresh raw response, re-run the same
hand-indexing process documented in the `parse_page()` docstring to find
the new field positions, and update the indices. Fallback if the endpoint
gets blocked outright: swap to a Playwright-based approach (`gosom/
google-maps-scraper` on GitHub is the best-maintained one) — much slower,
but resilient to markup/response changes since it reads the rendered page.
