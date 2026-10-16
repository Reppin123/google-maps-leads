# /// script
# requires-python = ">=3.9"
# dependencies = ["requests==2.32.3"]
# ///
"""
world_grid.py — population-weighted, self-refining grid search for ANY country.

Generalises au_grid.py. Instead of a hand-typed list of Australian cities, the
seed points come from GeoNames (cities500: every populated place on Earth with
500+ people, ~236k rows, CC-BY). Coverage is driven by population, not by a
person guessing which towns matter:

  half_width_km = 16 * sqrt(population / 1,000,000)     capped at 45 km

which reproduces the hand-tuned AU grid almost exactly (Sydney 5.6M → 38 km vs
35 hand-picked; Adelaide 1.5M → 19 vs 20; Hobart 250k → 8 vs 10; a 100k town →
one point). Suburbs that GeoNames lists as their own place (Logan City, Point
Cook, Tuggeranong…) are absorbed into the metro whose lattice already covers
them, so they don't double-scrape.

WHAT WAS WRONG WITH THE FIXED GRID (measured on 4,931 AU points, 10 keywords):
  36% of all points and ~50% of metro points returned Google's soft cap of
  120 results — i.e. the cell held MORE businesses than one viewport can show,
  and the fixed 6 km spacing silently undercounted every dense suburb.

SELF-REFINING: any point that returns the cap is split into 4 children at half
the spacing (6 → 3 → 1.5 km), up to --max-depth. Dense CBDs get dense coverage,
sparse suburbs stay cheap, and the same rule works for Lagos, Toronto or Leeds
without anyone tuning it. Regional towns (one point, avg 12–68 results, never
capped in AU) stay one point.

RESUMABLE: a run directory holds plan.json (frozen point list), state.json
(done / queued) and results.jsonl (append-only). Ctrl-C, a crash or a block
loses nothing; re-run with --resume. The final <keyword>_full.json is the same
shape au_grid.py produced, so pipeline.py ingests it unchanged.

BLEED FILTER: Google's geo-bias occasionally ignores the viewport and serves an
unlocalised batch (Punjab businesses in a Sydney run, 2026-09-15). AU used a
country bounding box; here every result farther than --max-dist-km (default
250) from its OWN viewport point is dropped, which works for any country and
also catches cross-border fallbacks. In AU regional data 90% of results sit
within 25 km of their point and p95 is 80 km.

BLOCK DETECTION: 429/503 back off (60s, 120s, 240s) then save + exit 3 with the
resume command. A run of consecutive empty points (Google's captcha page parses
as "no results") is treated the same way: 1 of 4,931 AU points was ever empty.

USAGE
  # what would a run cost? (no requests made)
  uv run --script world_grid.py plan --country NZ
  uv run --script world_grid.py plan --country US --admin1 CA          # one state
  uv run --script world_grid.py plan --near "Toronto" --country CA --radius-km 40
  uv run --script world_grid.py plan --bbox 51.2,-0.6,51.7,0.3         # lat_min,lng_min,lat_max,lng_max
  uv run --script world_grid.py plan --world --min-pop 100000          # the whole globe, big towns only

  # run it
  uv run --script world_grid.py run "plumbers" --country NZ --out-dir data/grid_nz_plumbers
  uv run --script world_grid.py run "plumbers" --country NZ --out-dir data/grid_nz_plumbers --resume

  # list the seeds a selector picks (sanity check before a long run)
  uv run --script world_grid.py seeds --country IE

SELECTORS (combine --country with --admin1 / --near; --bbox and --world stand alone)
  --country CC[,CC…]   ISO-3166 alpha-2, e.g. AU, GB, US, IN
  --admin1 CODE        GeoNames admin1 code inside --country (US states = 2 letters,
                       AU states = 01..08; `seeds` prints them)
  --near NAME          the most populous GeoNames place with that name (inside
                       --country if given) + --radius-km around it
  --bbox               any box, any country
  --world              every country (use --min-pop to keep it sane)
"""

import argparse
import io
import json
import math
import random
import re
import sys
import time
import zipfile
from pathlib import Path

import requests

import gmaps
from gmaps import search as gmaps_search

HERE = Path(__file__).resolve().parent
GEONAMES_DIR = HERE / "data" / "geonames"
CITIES_URL = "https://download.geonames.org/export/dump/cities500.zip"
COUNTRY_URL = "https://download.geonames.org/export/dump/countryInfo.txt"

KM_PER_DEG_LAT = 111.0
DEFAULT_SPACING_KM = 6.0      # proven in AU metros (avg 96 results/point)
DEFAULT_MIN_POP = 5000
DEFAULT_MAX_DEPTH = 2         # 6 → 3 → 1.5 km
DEFAULT_CAP = 120             # Google's soft cap per viewport (6 pages × 20)
DEFAULT_MAX_DIST_KM = 250.0
SINGLE_COVER_KM = 4.0         # a lone point is assumed to "own" this radius
SECONDS_PER_POINT_EST = 12.0  # ~5 pages × (pace + latency), measured in AU
EMPTY_STREAK_LIMIT = 10


# ─────────────────────────── geometry ───────────────────────────

def haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def km_to_deg(lat_deg, dx_km, dy_km):
    dlat = dy_km / KM_PER_DEG_LAT
    dlng = dx_km / (KM_PER_DEG_LAT * max(math.cos(math.radians(lat_deg)), 0.05))
    return dlng, dlat


def half_width_km(population):
    return min(45.0, 16.0 * math.sqrt(max(population, 0) / 1_000_000))


def lattice(center_lat, center_lng, hw_km, spacing_km):
    """Square lattice clipped to a circle of radius hw_km. hw < spacing → one point."""
    n = int(hw_km // spacing_km)
    pts = []
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            dx, dy = i * spacing_km, j * spacing_km
            if math.hypot(dx, dy) > hw_km:
                continue
            dlng, dlat = km_to_deg(center_lat, dx, dy)
            pts.append((center_lat + dlat, center_lng + dlng))
    return pts or [(center_lat, center_lng)]


# ─────────────────────────── GeoNames ───────────────────────────

def ensure_geonames():
    GEONAMES_DIR.mkdir(parents=True, exist_ok=True)
    cities = GEONAMES_DIR / "cities500.txt"
    countries = GEONAMES_DIR / "countryInfo.txt"
    if not cities.exists() or cities.stat().st_size < 1_000_000:
        print(f"Downloading GeoNames cities500 (~14 MB) → {cities}")
        raw = requests.get(CITIES_URL, timeout=180).content
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            cities.write_bytes(z.read("cities500.txt"))
    if not countries.exists() or countries.stat().st_size < 10_000:
        countries.write_bytes(requests.get(COUNTRY_URL, timeout=60).content)
    return cities, countries


def load_countries():
    _, path = ensure_geonames()
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        f = line.split("\t")
        if len(f) > 8:
            out[f[0]] = {"name": f[4], "population": int(f[7] or 0), "continent": f[8]}
    return out


def load_places(countries=None, min_pop=DEFAULT_MIN_POP):
    """Yield populated places from cities500 as dicts. countries = set of ISO2 or None (all)."""
    path, _ = ensure_geonames()
    wanted = {c.upper() for c in countries} if countries else None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 15 or f[6] != "P":
                continue
            cc = f[8]
            if wanted and cc not in wanted:
                continue
            try:
                pop = int(f[14] or 0)
            except ValueError:
                continue
            if pop < min_pop:
                continue
            yield {
                "geonameid": int(f[0]), "name": f[1], "ascii": f[2], "lat": float(f[4]),
                "lng": float(f[5]), "code": f[7], "cc": cc, "admin1": f[10], "population": pop,
            }


# ─────────────────────────── seeds → points ───────────────────────────

def select_places(args):
    if args.world:
        places = list(load_places(None, args.min_pop))
    elif args.bbox:
        lat_min, lng_min, lat_max, lng_max = args.bbox
        places = [p for p in load_places(None, args.min_pop)
                  if lat_min <= p["lat"] <= lat_max and lng_min <= p["lng"] <= lng_max]
    else:
        if not args.country:
            sys.exit("Pick a selector: --country, --bbox, --world (see --help)")
        ccs = [c.strip().upper() for c in args.country.split(",") if c.strip()]
        places = list(load_places(ccs, args.min_pop))
        if args.admin1:
            places = [p for p in places if p["admin1"].upper() == args.admin1.upper()]
        if args.near:
            # anchor = most populous place with that name, searched WITHOUT the min-pop floor
            cands = [p for p in load_places(ccs, 0)
                     if p["ascii"].lower() == args.near.lower() or p["name"].lower() == args.near.lower()]
            if not cands:
                sys.exit(f"No GeoNames place named {args.near!r} in {ccs}")
            anchor = max(cands, key=lambda p: p["population"])
            r = args.radius_km or 30.0
            places = [p for p in places if haversine_km(anchor["lat"], anchor["lng"], p["lat"], p["lng"]) <= r]
            if not any(p["geonameid"] == anchor["geonameid"] for p in places):
                places.append(anchor)
            args._anchor = anchor
    return places


def absorb(places):
    """Biggest first; a place already inside a bigger place's lattice is dropped."""
    places = sorted(places, key=lambda p: -p["population"])
    kept = []
    for p in places:
        hw = half_width_km(p["population"])
        absorbed = False
        for k in kept:
            reach = max(k["hw"], SINGLE_COVER_KM) + 2.0
            if haversine_km(k["lat"], k["lng"], p["lat"], p["lng"]) <= reach:
                k["absorbed"].append(p["name"])
                absorbed = True
                break
        if not absorbed:
            kept.append({**p, "hw": hw, "absorbed": []})
    return kept


def build_points(seeds, spacing_km):
    pts = []
    for s in seeds:
        label = f"{s['name']} {s['admin1']} {s['cc']}".strip()
        for lat, lng in lattice(s["lat"], s["lng"], s["hw"], spacing_km):
            pts.append({"lat": round(lat, 5), "lng": round(lng, 5), "label": label,
                        "seed": s["geonameid"], "depth": 0, "spacing": spacing_km})
    return pts


def children(pt):
    s = pt["spacing"] / 2.0
    out = []
    for i in (-1, 1):
        for j in (-1, 1):
            dlng, dlat = km_to_deg(pt["lat"], i * s / 2.0, j * s / 2.0)
            out.append({"lat": round(pt["lat"] + dlat, 5), "lng": round(pt["lng"] + dlng, 5),
                        "label": pt["label"], "seed": pt["seed"], "depth": pt["depth"] + 1, "spacing": s})
    return out


def point_id(pt):
    return f"{pt['lat']:.5f},{pt['lng']:.5f}"


def tier_of(pop):
    if pop >= 1_000_000:
        return "metro"
    if pop >= 150_000:
        return "city"
    if pop >= 30_000:
        return "town"
    return "small"


def summarise(seeds, points, args):
    by_tier = {}
    for s in seeds:
        t = tier_of(s["population"])
        by_tier.setdefault(t, []).append(s)
    print(f"Seeds: {len(seeds)} places (min pop {args.min_pop:,}), {len(points)} base points at {args.spacing} km")
    for t in ("metro", "city", "town", "small"):
        ss = by_tier.get(t, [])
        if not ss:
            continue
        n_pts = sum(len(lattice(s["lat"], s["lng"], s["hw"], args.spacing)) for s in ss)
        top = ", ".join(f"{s['name']} ({s['population']/1e6:.1f}M, {len(lattice(s['lat'], s['lng'], s['hw'], args.spacing))} pts)"
                        if s["population"] >= 1e6 else f"{s['name']} ({s['population']//1000}k)" for s in ss[:6])
        more = f" … +{len(ss)-6}" if len(ss) > 6 else ""
        print(f"  {t:5s}: {len(ss):5d} seeds → {n_pts:6d} points   {top}{more}")
    absorbed = sum(len(s["absorbed"]) for s in seeds)
    if absorbed:
        print(f"  absorbed into bigger neighbours: {absorbed} places")
    dense = sum(len(lattice(s["lat"], s["lng"], s["hw"], args.spacing))
                for s in seeds if s["population"] >= 150_000)
    est_refine = 0.5 * 4 * dense if args.max_depth >= 1 else 0   # AU: ~50% of metro/city points capped
    total = len(points) + est_refine
    hrs = total * SECONDS_PER_POINT_EST / 3600
    print(f"Estimate: ~{int(total):,} points incl. refinement ({dense} dense points × AU-measured 50% cap rate × 4), "
          f"~{hrs:.1f} h per keyword at default pace")


# ─────────────────────────── run ───────────────────────────

class Blocked(Exception):
    pass


def run(args):
    keyword = args.keyword
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path, state_path, results_path = out_dir / "plan.json", out_dir / "state.json", out_dir / "results.jsonl"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", keyword).strip("_").lower()

    if args.resume and not plan_path.exists():
        sys.exit(f"--resume: no plan.json in {out_dir}; start the run without --resume")
    if args.resume:
        plan = json.load(open(plan_path))
        state = json.load(open(state_path)) if state_path.exists() else {"done": [], "queue": []}
        points = plan["points"]
        print(f"Resuming: {len(state['done'])} of {len(points)} base points done, {len(state['queue'])} refinements queued")
    else:
        seeds = absorb(select_places(args))
        points = build_points(seeds, args.spacing)
        if args.max_points:
            points = points[: args.max_points]
        plan = {"keyword": keyword, "args": {k: v for k, v in vars(args).items() if not k.startswith("_") and k != "func"},
                "seeds": [{k: s[k] for k in ("geonameid", "name", "cc", "admin1", "lat", "lng", "population", "hw")} for s in seeds],
                "points": points, "created": time.strftime("%Y-%m-%dT%H:%M:%S")}
        json.dump(plan, open(plan_path, "w"), indent=1)
        state = {"done": [], "queue": []}
        results_path.write_text("")
        summarise(seeds, points, args)

    seed_by_id = {s["geonameid"]: s for s in plan["seeds"]}
    ccs = sorted({s["cc"] for s in plan["seeds"]})
    if len(ccs) == 1:
        gmaps.ACCEPT_LANGUAGE = f"en-{ccs[0]},en;q=0.9"

    done = set(state["done"])
    # state["queue"] already holds the not-yet-done base points (save_state stores the
    # live queue), so re-adding them from plan["points"] double-queued every remaining
    # point (Delhi 2026-09-18: 147 left → 294 run, second half all 0 new). Dedupe by id.
    queue, queued = [], set()
    for p in [p for p in points if point_id(p) not in done] + state["queue"]:
        if point_id(p) not in queued:
            queue.append(p); queued.add(point_id(p))
    session = requests.Session()
    seen_ids = set()
    if results_path.exists():
        for line in open(results_path):
            try:
                seen_ids.add(json.loads(line).get("place_id"))
            except json.JSONDecodeError:
                pass
    stats = {"points": 0, "capped": 0, "dropped_far": 0, "new": 0, "empty_streak": 0}
    backoffs = [60, 120, 240]
    t0 = time.time()

    def save_state():
        json.dump({"done": sorted(done), "queue": queue}, open(state_path, "w"))

    def finish():
        merged, ids = [], set()
        for line in open(results_path):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = r.get("place_id") or r.get("name")
            if key in ids:
                continue
            ids.add(key)
            merged.append(r)
        out_path = out_dir / f"{slug}_full.json"
        json.dump(merged, open(out_path, "w"), indent=2)
        return out_path, len(merged)

    print(f"Run: '{keyword}', {len(queue)} points to go, cap {args.cap}, refine to depth {args.max_depth}")
    try:
        with open(results_path, "a") as sink:
            while queue:
                pt = queue[0]
                pid = point_id(pt)
                results = None
                for attempt, wait in enumerate([0] + backoffs):
                    if wait:
                        print(f"  blocked/unavailable, backing off {wait}s (attempt {attempt}/{len(backoffs)})")
                        save_state()
                        time.sleep(wait)
                    try:
                        results = gmaps_search(keyword, max_results=args.cap, pace=(args.pace, args.pace + 1.3),
                                               verbose=False, center=(pt["lat"], pt["lng"]), session=session)
                        break
                    except requests.HTTPError as e:
                        code = getattr(e.response, "status_code", None)
                        if code not in (429, 503):
                            print(f"  {pt['label']} d{pt['depth']}: HTTP {code} — skipping point")
                            results = []
                            break
                    except requests.RequestException as e:
                        print(f"  {pt['label']} d{pt['depth']}: {e} — retrying")
                if results is None:
                    raise Blocked("HTTP 429/503 persisted through all back-offs")

                kept = new = far = 0
                for r in results:
                    if r.get("lat") is None:
                        continue
                    d = haversine_km(pt["lat"], pt["lng"], r["lat"], r["lng"])
                    if d > args.max_dist_km:
                        far += 1
                        continue
                    kept += 1
                    key = r.get("place_id") or r.get("name")
                    if key in seen_ids:
                        continue
                    seen_ids.add(key)
                    r["_query"] = keyword
                    r["_grid_point"] = pt["label"]
                    r["_point_lat"], r["_point_lng"], r["_point_depth"] = pt["lat"], pt["lng"], pt["depth"]
                    r["_point_dist_km"] = round(d, 1)
                    seed = seed_by_id.get(pt["seed"], {})
                    r["_area"] = seed.get("name")          # e.g. "Auckland", "Los Angeles", "Sydney"
                    r["_cc"] = seed.get("cc")
                    if args.profile:
                        r["_profile"] = args.profile
                    if args.tier_num:
                        r["_tier"] = args.tier_num
                    sink.write(json.dumps(r, ensure_ascii=False) + "\n")
                    new += 1
                sink.flush()

                queue.pop(0)
                done.add(pid)
                stats["points"] += 1
                stats["new"] += new
                stats["dropped_far"] += far
                # Saturated only if the IN-RANGE results fill the cap. When a category is
                # sparse Google pads the 120 with far-away matches (Delhi "sports
                # wholesalers": 47 of 120 were >250 km away); that is exhausted local
                # supply, not hidden density, so it must not trigger a split.
                capped = kept >= args.cap
                refined = ""
                if capped:
                    stats["capped"] += 1
                    # Split only while splitting pays: a child that is still capped but
                    # added <15% new businesses is overlap, not undiscovered density
                    # (Auckland smoke 2026-09-18: depth-1 children added 0-10 of 60).
                    worth_it = pt["depth"] == 0 or new >= 0.15 * len(results)
                    if pt["depth"] < args.max_depth and worth_it:
                        kids = [c for c in children(pt) if point_id(c) not in done]
                        queue.extend(kids)
                        refined = f" → split into {len(kids)} at {pt['spacing']/2:.2g} km"
                stats["empty_streak"] = stats["empty_streak"] + 1 if len(results) == 0 else 0
                el = (time.time() - t0) / 60
                print(f"  [{stats['points']}/{stats['points']+len(queue)}] {pt['label']} d{pt['depth']}: "
                      f"{len(results)} results, {new} new (total {len(seen_ids)}, {el:.1f}m)"
                      f"{' FAR-DROPPED '+str(far) if far else ''}{refined}")
                if stats["points"] % 10 == 0:
                    save_state()
                if stats["empty_streak"] >= EMPTY_STREAK_LIMIT and stats["points"] > EMPTY_STREAK_LIMIT:
                    raise Blocked(f"{EMPTY_STREAK_LIMIT} consecutive empty points — Google is probably serving its captcha page")
                time.sleep(random.uniform(args.pace, args.pace + 1.3))
    except KeyboardInterrupt:
        save_state()
        out_path, n = finish()
        print(f"\nInterrupted. {stats['points']} points done this session, {n} unique so far → {out_path}")
        print(f"Resume with:  uv run --script world_grid.py run \"{keyword}\" --out-dir {out_dir} --resume")
        sys.exit(130)
    except Blocked as e:
        save_state()
        out_path, n = finish()
        print(f"\nSTOPPED: {e}. State saved; {n} unique so far → {out_path}")
        print(f"Wait a while, then:  uv run --script world_grid.py run \"{keyword}\" --out-dir {out_dir} --resume")
        sys.exit(3)

    save_state()
    out_path, n = finish()
    print(f"\nDone: {n} unique businesses; {stats['points']} points this session, {stats['capped']} capped, "
          f"{stats['dropped_far']} far results dropped → {out_path}")


# ─────────────────────────── CLI ───────────────────────────

def add_selectors(ap):
    ap.add_argument("--country", help="ISO2 code(s), comma-separated: AU, GB, US, IN")
    ap.add_argument("--admin1", help="admin1 code inside --country (US: CA, TX; AU: 01..08)")
    ap.add_argument("--near", help="place name; combine with --radius-km")
    ap.add_argument("--radius-km", type=float, default=None)
    ap.add_argument("--bbox", type=lambda s: [float(x) for x in s.split(",")],
                    help="lat_min,lng_min,lat_max,lng_max")
    ap.add_argument("--world", action="store_true")
    ap.add_argument("--min-pop", type=int, default=DEFAULT_MIN_POP)
    ap.add_argument("--spacing", type=float, default=DEFAULT_SPACING_KM, help="base lattice spacing km")
    ap.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH, help="refinement depth on capped points")


def cmd_plan(args):
    seeds = absorb(select_places(args))
    points = build_points(seeds, args.spacing)
    summarise(seeds, points, args)
    if args.json:
        json.dump({"seeds": seeds, "points": points}, open(args.json, "w"), indent=1)
        print(f"Wrote {args.json}")


def cmd_seeds(args):
    seeds = absorb(select_places(args))
    countries = load_countries()
    print(f"{'place':32s} {'cc':2s} {'adm1':5s} {'pop':>10s} {'hw km':>6s} {'pts':>4s}  absorbed")
    for s in seeds:
        n = len(lattice(s["lat"], s["lng"], s["hw"], args.spacing))
        ab = ", ".join(s["absorbed"][:4]) + (f" +{len(s['absorbed'])-4}" if len(s["absorbed"]) > 4 else "")
        print(f"{s['name'][:32]:32s} {s['cc']:2s} {s['admin1'][:5]:5s} {s['population']:>10,d} {s['hw']:6.1f} {n:4d}  {ab}")
    ccs = sorted({s["cc"] for s in seeds})
    print(f"\n{len(seeds)} seeds in " + ", ".join(f"{c} ({countries.get(c, {}).get('name', '?')})" for c in ccs))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="show seeds, point count and time estimate; no requests")
    add_selectors(p)
    p.add_argument("--json", help="also write the seeds+points to this file")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("seeds", help="list the seed places a selector picks")
    add_selectors(p)
    p.set_defaults(func=cmd_seeds)

    p = sub.add_parser("run", help="scrape a keyword across the grid (resumable)")
    p.add_argument("keyword")
    add_selectors(p)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--resume", action="store_true")
    p.add_argument("--cap", type=int, default=DEFAULT_CAP, help="results per point that counts as 'capped'")
    p.add_argument("--max-dist-km", type=float, default=DEFAULT_MAX_DIST_KM)
    p.add_argument("--pace", type=float, default=1.3)
    p.add_argument("--max-points", type=int, default=None, help="truncate the base plan (smoke tests)")
    p.add_argument("--profile", default=None)
    p.add_argument("--tier-num", type=int, default=None)
    p.set_defaults(func=run)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
