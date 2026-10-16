# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
dashboard-kit — build a self-contained dashboard from a dataset in one pass.

A project is a folder with two files the model writes:

    dashboard.spec.json   what the fields are, which views/facets/charts/KPIs, the pipeline
    adapter.py            def load_rows(project_dir) -> (rows: list[dict], meta: dict)

Everything else is this kit: profiling, normalising, dedup, encoding, the renderer
(template.html + vendored libraries), the self-test, the headless verifier, the
annotations round-trip. A new dataset changes the spec and the adapter, never the kit.

    uv run --script kit.py build <project>          # -> <project>/dashboard/index.html
    uv run --script kit.py selftest <project>       # headless Chrome at 1440 and 500 wide; exit 1 on any failure
    uv run --script kit.py screenshots <project>    # default / filtered / board / charts / narrow
    uv run --script kit.py verify <project>         # build + selftest + screenshots
    uv run --script kit.py import-annotations <project> <file.json>
    uv run --script kit.py schema                   # print the spec contract
    uv run --script kit.py new <project> --title "…" # scaffold spec + adapter from a first guess

Lessons folded in as code (so no build has to relearn them):
  read-only sources, provenance from the adapter not the file mtime, sentinel and
  empty-value normalisation, tags as rows-not-pairs, dedup on native keys, coordinates
  validated, dictionary-coded enums + trailing-null trim, one central sort owner,
  MiniSearch string ids, index after first paint, hidden rule, min-width:0, outline
  totals, coverage-gated charts, empty-state for all-zero columns, headless Chrome that
  does not hang (per-run profile, Singleton cleared, output polled, process group killed),
  the 500-px clamp, both widths, cross-surface agreement as a mandatory check.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import signal
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

KIT_VERSION = "1.0.0"
KIT_DIR = Path(__file__).resolve().parent
TEMPLATE = KIT_DIR / "template.html"
VENDOR = KIT_DIR / "vendor"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

VENDOR_CSS = ["tabulator.min.css", "leaflet.css", "markercluster.css", "markercluster.default.css"]
VENDOR_JS = ["tabulator.min.js", "leaflet.js", "markercluster.js", "chart.umd.js", "minisearch.js",
             "sortable.min.js", "lz-string.min.js"]

EMPTY = {None, "", "null", "None", "NONE", "N/A", "n/a", "NA", "na", "NIL", "nil", "-", "—", "–", "..", "?"}
TYPES = {"id", "text", "longtext", "enum", "tags", "number", "flag", "url", "email", "phone", "datetime", "date"}
CHARTS = {"bar", "topn", "ordinal", "histogram"}
VIEWS = {"table", "board", "map", "charts"}

SCHEMA = """dashboard.spec.json — the contract (kit %s)

{
  "kit": 1,
  "dataset_id": "acme-nz-leads",              # slug; namespaces browser storage and the annotations file
  "title": "Acme NZ leads",
  "subtitle": "one line, optional",
  "id_field": "place_id",                     # the source's own id; rows are keyed on it
  "display_field": "name",                    # the human name, never an id
  "freshness_field": "last_seen",             # optional; meta.pulled_max wins when present
  "geo": {"lat": "lat", "lng": "lng", "min_coverage": 0.01},   # optional; map view only if coverage >= min
  "dedup_keys": ["phone", "website_host"],   # optional; same normalised value = one duplicate group
  "hide_by_default": {"field": "status", "values": ["Closed"]},  # optional; a toolbar toggle shows them
  "drop_fields": ["photo"],                   # optional; never reach the page
  "fields": [
    {"key": "name", "label": "Business", "type": "text", "pin": true, "search": 3},
    {"key": "profile", "label": "ICP profile", "type": "enum", "facet": true, "chart": "bar", "color": true},
    {"key": "categories", "label": "Categories", "type": "tags", "facet": true, "search": 1, "column": false},
    {"key": "rating", "label": "Rating", "type": "number", "range": true, "chart": "ordinal", "format": "rating"},
    {"key": "review_count", "label": "Reviews", "short": "Rev", "type": "number", "chart": "histogram", "log": true, "range": true},
    {"key": "has_email", "label": "Has email", "type": "flag", "derived": "email"},   # flag computed from another field
    {"key": "state", "label": "State", "type": "enum", "facet": true, "note": "derived from coordinates where no address"},
    {"key": "website", "label": "Website", "type": "url"},
    {"key": "last_seen", "label": "Last pulled", "type": "datetime", "column": false}
  ],
  # field keys: key label type · short (header) · facet · chart bar|topn|ordinal|histogram · log · range ·
  #             format int|rating|money|pct · note (shown as ⓘ) · derived (true or a source field) · pin ·
  #             search (weight 1-4) · column false (drawer only) · hidden · min_coverage (chart gate, default .05)
  "links": {"maps": "https://www.google.com/maps/place/?q=place_id:{place_id}"},
  "default_sort": [{"field": "signal_score", "dir": "desc"}, {"field": "review_count", "dir": "desc"}],
  "default_view": "table",
  "views": ["table", "board", "map", "charts"],
  "pipeline": ["New", "Queued", "Contacted", "Replied", "Qualified", "Won", "Lost"],   # [] = no board layer
  "closed_stages": ["Won", "Lost"],
  "kpis": ["rows", "stages", "overdue", "coverage", "median:rating", "freshness", "duplicates"],
  "saved_views": [{"name": "No website, has phone", "state": {"filters": {"has_website": ["0"], "has_phone": ["1"]}}}]
}

adapter.py — def load_rows(project_dir: Path) -> tuple[list[dict], dict]
  rows: one dict per record, keys = field keys (extra keys are dropped; missing keys become null)
  meta: {"source": "leads.db", "pulled_min": "...", "pulled_max": "...", "notes": ["..."]}
  Read sources read-only. Derive fields here (state from coordinates, junk emails set aside) and
  declare them derived in the spec. Never write annotations into the source store.
""" % KIT_VERSION


# --------------------------------------------------------------------------- spec
def load_spec(project: Path) -> dict:
    p = project / "dashboard.spec.json"
    if not p.exists():
        raise SystemExit(f"no dashboard.spec.json in {project} — run `kit.py schema` for the contract")
    spec = json.loads(p.read_text(encoding="utf-8"))
    validate_spec(spec)
    return spec


def validate_spec(spec: dict) -> None:
    errs = []
    for k in ("dataset_id", "title", "id_field", "display_field", "fields"):
        if k not in spec:
            errs.append(f"missing '{k}'")
    keys = set()
    for f in spec.get("fields", []):
        if "key" not in f or "type" not in f:
            errs.append(f"field without key/type: {f}")
            continue
        if f["type"] not in TYPES:
            errs.append(f"field {f['key']}: unknown type {f['type']} (one of {sorted(TYPES)})")
        if f.get("chart") and f["chart"] not in CHARTS:
            errs.append(f"field {f['key']}: unknown chart {f['chart']} (one of {sorted(CHARTS)})")
        if f["key"] in keys:
            errs.append(f"duplicate field key {f['key']}")
        keys.add(f["key"])
    for req in ("id_field", "display_field"):
        if spec.get(req) and spec[req] not in keys:
            errs.append(f"{req} '{spec[req]}' is not a declared field")
    for v in spec.get("views", ["table"]):
        if v not in VIEWS:
            errs.append(f"unknown view {v}")
    geo = spec.get("geo")
    if geo and (geo.get("lat") not in keys or geo.get("lng") not in keys):
        errs.append("geo.lat / geo.lng must be declared fields")
    for s in spec.get("default_sort", []):
        if s.get("field") not in keys:
            errs.append(f"default_sort field {s.get('field')} is not a declared field")
    known_top = {"kit", "dataset_id", "title", "subtitle", "id_field", "display_field", "freshness_field", "geo",
                 "dedup_keys", "hide_by_default", "drop_fields", "fields", "links", "default_sort", "default_view",
                 "views", "pipeline", "closed_stages", "kpis", "saved_views", "junk_email_domains", "auto_stages"}
    for k in spec:
        if k not in known_top:
            errs.append(f"unknown top-level key '{k}'")
    if errs:
        raise SystemExit("spec invalid:\n  - " + "\n  - ".join(errs))


def load_adapter(project: Path):
    p = project / "adapter.py"
    if not p.exists():
        raise SystemExit(f"no adapter.py in {project} — it must define load_rows(project_dir)")
    s = importlib.util.spec_from_file_location("adapter", p)
    mod = importlib.util.module_from_spec(s)
    s.loader.exec_module(mod)  # type: ignore[union-attr]
    if not hasattr(mod, "load_rows"):
        raise SystemExit("adapter.py has no load_rows(project_dir)")
    return mod


# --------------------------------------------------------------------------- normalise
def _norm(v):
    if isinstance(v, (list, dict)):
        return v or None
    if isinstance(v, str):
        v = v.strip()
    try:
        return None if v in EMPTY else v
    except TypeError:
        return v


def _host(url) -> str | None:
    if not url:
        return None
    try:
        h = urlsplit(url if "://" in str(url) else "http://" + str(url)).hostname or ""
    except ValueError:
        return None
    return h.lower().removeprefix("www.") or None


def _to_number(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        s = re.sub(r"[,$£€₹\s]|[a-zA-Z%]+$", "", v.strip())
        try:
            return float(s) if "." in s else int(s)
        except ValueError:
            return None
    return None


def _to_tags(v):
    if v is None:
        return None
    if isinstance(v, list):
        out = [str(x).strip() for x in v if str(x).strip()]
        return out or None
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("["):
            try:
                return _to_tags(json.loads(s))
            except ValueError:
                pass
        parts = [p.strip() for p in re.split(r"[;|,]", s) if p.strip()]
        return parts or None
    return None


def _to_flag(v):
    if v is None:
        return None
    if isinstance(v, str):
        return 1 if v.strip().lower() in ("1", "true", "yes", "y") else 0
    return 1 if v else 0


def normalise(rows: list[dict], spec: dict) -> tuple[list[dict], dict]:
    fields = spec["fields"]
    fk = {f["key"]: f for f in fields}
    drop = set(spec.get("drop_fields", []))
    junk = tuple(spec.get("junk_email_domains", []))
    geo = spec.get("geo")
    report = {"bad_geo": 0, "junk_email": 0, "coerce_fail": Counter()}
    out = []
    for r in rows:
        row = {}
        for f in fields:
            k = f["key"]
            if k in drop:
                continue
            v = _norm(r.get(k))
            t = f["type"]
            if t == "number":
                n = _to_number(v)
                if v is not None and n is None:
                    report["coerce_fail"][k] += 1
                v = n
            elif t == "tags":
                v = _to_tags(v)
            elif t == "flag" and not f.get("derived"):
                v = _to_flag(v)
            elif t == "email" and v and junk and any(d in str(v).lower() for d in junk):
                row[k + "_raw"] = v
                v = None
                report["junk_email"] += 1
            row[k] = v
        for f in fields:  # derived flags computed from another field, after the base pass
            if f["type"] == "flag" and isinstance(f.get("derived"), str):
                src = row.get(f["derived"])
                row[f["key"]] = 1 if (src not in (None, 0, "", []) ) else 0
        if geo:
            lat, lng = row.get(geo["lat"]), row.get(geo["lng"])
            ok = isinstance(lat, (int, float)) and isinstance(lng, (int, float)) and -90 <= lat <= 90 and -180 <= lng <= 180 and not (lat == 0 and lng == 0)
            if not ok and (lat is not None or lng is not None):
                report["bad_geo"] += 1
            if not ok:
                row[geo["lat"]] = row[geo["lng"]] = None
        out.append(row)
    # duplicate groups on normalised keys
    groups: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(out):
        for key in spec.get("dedup_keys", []):
            if key == "website_host":
                v = _host(row.get("website"))
                if v in ("facebook.com", "instagram.com", "linkedin.com", "google.com"):
                    v = None
            elif key == "phone":
                d = re.sub(r"\D", "", str(row.get("phone") or ""))
                v = d if len(d) >= 8 else None
            else:
                v = str(row.get(key)).strip().lower() if row.get(key) not in (None, "") else None
            if v:
                groups[key + ":" + v].append(i)
    gid = 0
    for i in range(len(out)):
        out[i]["_dup"] = None
    for members in groups.values():
        if len(members) > 1:
            gid += 1
            for i in members:
                if out[i]["_dup"] is None:
                    out[i]["_dup"] = gid
    report["dup_groups"] = gid
    report["dup_rows"] = sum(1 for r in out if r["_dup"])
    report["coerce_fail"] = dict(report["coerce_fail"])
    return out, report


# --------------------------------------------------------------------------- profile
def profile(rows: list[dict], spec: dict) -> dict:
    n = len(rows) or 1
    prof = {}
    for f in spec["fields"]:
        k = f["key"]
        vals = [r.get(k) for r in rows]
        filled = [v for v in vals if v not in (None, "", [], 0) or (f["type"] == "number" and v == 0)]
        e = {"fill": round(len(filled) / n, 4), "nonzero": sum(1 for v in filled if v not in (0, "0", False))}
        if f["type"] in ("enum", "flag", "tags"):
            c = Counter()
            for v in filled:
                for x in (v if isinstance(v, list) else [v]):
                    c[str(x)] += 1
            e["distinct"] = len(c)
            e["top"] = c.most_common(5)
            # sentinel tell: one exact value on a large share of rows
            # sentinel tell: one exact value on nearly every row of an enum with real variety (never tags/flags)
            if c and f["type"] == "enum" and c.most_common(1)[0][1] / n > 0.85 and len(c) > 3:
                e["sentinel_suspect"] = c.most_common(1)[0][0]
        elif f["type"] == "number":
            nums = [v for v in filled if isinstance(v, (int, float))]
            if nums:
                e.update(min=min(nums), max=max(nums), median=statistics.median(nums), distinct=len(set(nums)))
                cc = Counter(nums).most_common(1)[0]
                if len(nums) > 20 and cc[1] / len(nums) > 0.6 and len(set(nums)) > 8:
                    e["sentinel_suspect"] = cc[0]
        else:
            e["distinct"] = len(set(map(str, filled)))
            if e["distinct"] <= 2 and e["fill"] > 0.9 and f["type"] in ("text", "longtext"):
                e["boilerplate_suspect"] = True
        prof[k] = e
    return prof


def schema_card(spec: dict, rows: list[dict], prof: dict, meta: dict, report: dict) -> str:
    lines = [f"# {spec['title']} — schema card (kit {KIT_VERSION})",
             f"rows {len(rows):,} · source {meta.get('source', '?')} · pulled {meta.get('pulled_min', '?')} → {meta.get('pulled_max', '?')}",
             f"duplicate groups {report.get('dup_groups', 0):,} ({report.get('dup_rows', 0):,} rows) · bad coordinates {report.get('bad_geo', 0)} · junk emails set aside {report.get('junk_email', 0)}"]
    for n in meta.get("notes", []):
        lines.append(f"! {n}")
    for k, c in report.get("coerce_fail", {}).items():
        lines.append(f"! {k}: {c} values could not be read as numbers")
    for f in spec["fields"]:
        if f.get("hidden"):
            continue
        p = prof[f["key"]]
        extra = ""
        if "top" in p:
            extra = "  top: " + ", ".join(f"{v} ({c:,})" for v, c in p["top"][:4])
        elif "min" in p:
            extra = f"  min {p['min']} · median {p['median']} · max {p['max']}"
        flag = ""
        if p.get("sentinel_suspect") is not None:
            flag = f"  ⚠ one value repeats on most rows ({p['sentinel_suspect']}): sentinel?"
        if p.get("boilerplate_suspect"):
            flag = "  ⚠ fill high, distinct ≤2: boilerplate?"
        lines.append(f"  {f['key']:18} {f['type']:8} fill {p['fill']:6.1%}  distinct {p.get('distinct', 0):>6,}{extra}{flag}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- encode
def encode(rows: list[dict], spec: dict) -> dict:
    """Columnar, dictionary-coded enums/tags, trailing nulls trimmed. The page decodes once."""
    keys = [f["key"] for f in spec["fields"] if f["key"] not in set(spec.get("drop_fields", []))]
    extra = ["_dup"] + [k + "_raw" for k in keys if any(k + "_raw" in r for r in rows[:50])]
    keys = keys + extra
    fk = {f["key"]: f for f in spec["fields"]}
    dicts: dict[str, dict] = {}
    coded = set()
    for k in keys:
        f = fk.get(k)
        if f and f["type"] in ("enum", "tags"):
            coded.add(k)
            dicts[k] = {}
    out_rows = []
    for r in rows:
        arr = []
        for k in keys:
            v = r.get(k)
            if k in coded and v is not None:
                d = dicts[k]
                if isinstance(v, list):
                    v = [d.setdefault(str(x), len(d)) for x in v]
                else:
                    v = d.setdefault(str(v), len(d))
            arr.append(v)
        while arr and arr[-1] is None:
            arr.pop()
        out_rows.append(arr)
    return {"fields": keys, "coded": {k: [None] * len(d) for k, d in dicts.items()}, "rows": out_rows,
            "_dicts": dicts}


def finalise_encoding(enc: dict) -> dict:
    for k, d in enc.pop("_dicts").items():
        arr = enc["coded"][k]
        for val, idx in d.items():
            arr[idx] = val
    return enc


# --------------------------------------------------------------------------- build
def build(project: Path, quiet: bool = False, host: dict | None = None, annotations: dict | None = None):
    """Writes dashboard/index.html, a file that works alone. With `host` (the app is serving the
    page) nothing is written: the page is returned, and stages and notes come from `annotations`."""
    t0 = time.time()
    spec = load_spec(project)
    adapter = load_adapter(project)
    rows_raw, meta = adapter.load_rows(project)
    if not isinstance(rows_raw, list) or not isinstance(meta, dict):
        raise SystemExit("adapter.load_rows must return (rows: list[dict], meta: dict)")
    rows, report = normalise(rows_raw, spec)
    prof = profile(rows, spec)
    if not quiet:
        print(schema_card(spec, rows, prof, meta, report))
    out_dir = project / "dashboard"
    out_dir.mkdir(exist_ok=True)
    ann_path = out_dir / "annotations.json"
    ann = annotations or {}
    if annotations is None and ann_path.exists():
        try:
            ann = json.loads(ann_path.read_text(encoding="utf-8")).get("annotations", {})
        except ValueError:
            pass
    enc = finalise_encoding(encode(rows, spec))
    geo = spec.get("geo")
    geo_cov = (sum(1 for r in rows if r.get(geo["lat"]) is not None) / (len(rows) or 1)) if geo else 0
    views = [v for v in spec.get("views", ["table", "charts"]) if not (v == "map" and (not geo or geo_cov < geo.get("min_coverage", 0.01)))]
    if spec.get("views") and "map" in spec["views"] and "map" not in views and not quiet:
        print(f"map view dropped: coordinates on {geo_cov:.1%} of rows")
    if not spec.get("pipeline"):
        views = [v for v in views if v != "board"]
    bundle = {"kit": KIT_VERSION, "spec": {**spec, "views": views}, "profile": prof, "annotations": ann, "host": host,
              "meta": {**meta, "rows": len(rows), "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "report": report, "geo_coverage": round(geo_cov, 4)}}
    country = ""
    if (project / "project.json").exists():
        country = json.loads((project / "project.json").read_text()).get("country", "")
    au = country in ("", "AU")            # the only outline shipped so far; elsewhere the map has tiles and pins only
    outline = ((VENDOR / "au-states.geojson").read_text(encoding="utf-8") if au else
               '{"type":"FeatureCollection","features":[]}') if "map" in views else "null"
    css = "\n".join((VENDOR / f).read_text(encoding="utf-8") for f in VENDOR_CSS)
    js = "\n;\n".join((VENDOR / f).read_text(encoding="utf-8") for f in VENDOR_JS)
    html = TEMPLATE.read_text(encoding="utf-8")
    esc = lambda s: s.replace("</", "<\\/")
    for needle, value in (("/*__VENDOR_CSS__*/", css), ("/*__VENDOR_JS__*/", js),
                          ("__BUNDLE_JSON__", esc(json.dumps(bundle, separators=(",", ":"), ensure_ascii=False))),
                          ("__DATA_JSON__", esc(json.dumps(enc, separators=(",", ":"), ensure_ascii=False))),
                          ("__OUTLINE_JSON__", esc(outline)), ("__TITLE__", spec["title"])):
        if needle not in html:
            raise SystemExit(f"template is missing {needle}")
        html = html.replace(needle, value)
    ext = re.findall(r'<(?:script|link|img|iframe)\b[^>]*?(?:src|href)=["\'](https?://[^"\']+)', html)
    if ext:
        raise SystemExit(f"external resources in output: {ext[:5]}")
    if host:
        return html
    out = out_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    (out_dir / "build.json").write_text(json.dumps({"kit": KIT_VERSION, "built_at": bundle["meta"]["built_at"], "rows": len(rows),
                                                    "bytes": out.stat().st_size, "views": views}, indent=1), encoding="utf-8")
    if not quiet:
        print(f"\nwrote {out} — {out.stat().st_size / 1e6:.1f} MB · {len(rows):,} rows · views {', '.join(views)} · {time.time() - t0:.1f}s")
        if out.stat().st_size > 60e6:
            print("! over 60 MB: move the data to a sidecar tier (see the playbook)")
    return out


# --------------------------------------------------------------------------- annotations
def import_annotations(project: Path, path: Path) -> None:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    incoming = raw.get("annotations", raw)
    out_dir = project / "dashboard"
    out_dir.mkdir(exist_ok=True)
    dest = out_dir / "annotations.json"
    cur = {}
    if dest.exists():
        try:
            cur = json.loads(dest.read_text(encoding="utf-8")).get("annotations", {})
        except ValueError:
            pass
    n = 0
    for rid, a in incoming.items():
        c = cur.get(rid)
        if c and c.get("updated_at") and a.get("updated_at") and c["updated_at"] >= a["updated_at"]:
            continue
        cur[rid] = a
        n += 1
    dest.write_text(json.dumps({"dataset_id": None, "imported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                                "annotations": cur}, indent=1), encoding="utf-8")
    print(f"merged {n} annotation(s) into {dest} (last write wins); rebuild to embed them")


# --------------------------------------------------------------------------- headless chrome
def _chrome(args: list[str], out_path: Path | None, timeout: int = 150, width: int = 1440, height: int = 900) -> str:
    """Run headless Chrome once and get its output reliably.

    Chrome writes its output and then often does not exit; its children hold the stdout
    pipe, so `subprocess.run(timeout=)` can block forever; a killed run leaves Singleton*
    files that make the next run abort with an empty page. So: a fresh profile per run,
    stdout to a file, poll the output for size stability, then kill the process group.
    Widths under ~500 px are clamped by headless Chrome on macOS; do not ask for 400.
    """
    if not Path(CHROME).exists():
        raise SystemExit("Google Chrome not found at " + CHROME)
    prof = Path("/tmp") / f"dashboard-kit-chrome-{os.getpid()}-{int(time.time() * 1000)}"
    shutil.rmtree(prof, ignore_errors=True)
    prof.mkdir(parents=True)
    log = prof / "stdout.txt"
    cmd = [CHROME, "--headless=new", "--disable-gpu", "--no-first-run", f"--user-data-dir={prof}",
           f"--window-size={max(500, width)},{height}", "--hide-scrollbars", *args]
    with open(log, "wb") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.DEVNULL, start_new_session=True)
    target = out_path or log
    t, last, stable = time.time(), -1, 0
    while time.time() - t < timeout:
        time.sleep(1.0)
        sz = target.stat().st_size if target.exists() else 0
        stable = stable + 1 if (sz > 0 and sz == last) else 0
        last = sz
        if stable >= 2 or proc.poll() is not None and sz > 0:
            break
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        pass
    time.sleep(0.3)
    text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    shutil.rmtree(prof, ignore_errors=True)
    return text


def selftest(project: Path) -> int:
    out = project / "dashboard" / "index.html"
    if not out.exists():
        raise SystemExit("build first")
    ok_all = True
    for width in (1440, 500):
        dom = _chrome(["--virtual-time-budget=20000", "--dump-dom", f"file://{out}#selftest"], None, width=width)
        m = re.search(r'<pre id="selftest"[^>]*>(.*?)</pre>', dom, re.S)
        if not m:
            print(f"[{width}px] no #selftest block in the DOM — the page did not finish or threw before boot")
            ok_all = False
            continue
        text = m.group(1).replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        try:
            rep = json.loads(text)
        except ValueError:
            print(f"[{width}px] selftest output is not JSON:\n{text[:800]}")
            ok_all = False
            continue
        fails = [c for c in rep["checks"] if not c["ok"]]
        print(f"[{width}px] {'OK' if rep['ok'] else 'FAIL'} — {len(rep['checks']) - len(fails)}/{len(rep['checks'])} checks · interactive {rep['perf'].get('interactive_ms')} ms (virtual clock: synchronous timings read 0)")
        for c in fails:
            print(f"   FAIL {c['name']}: {c.get('info')}")
        if rep.get("errors"):
            print("   errors:", rep["errors"])
        ok_all = ok_all and rep["ok"]
    (project / "dashboard" / "selftest.txt").write_text(f"{'ok' if ok_all else 'fail'} {datetime.now(timezone.utc).isoformat(timespec='seconds')}\n", encoding="utf-8")
    return 0 if ok_all else 1


def screenshots(project: Path) -> None:
    out = project / "dashboard" / "index.html"
    spec = load_spec(project)
    first_enum = next((f["key"] for f in spec["fields"] if f.get("facet") and f["type"] == "enum"), None)
    shots = {"default": ("1440,900", ""), "charts": ("1440,900", "#v=" + json.dumps({"view": "charts"})),
             "narrow": ("500,900", "")}
    if spec.get("pipeline"):
        shots["board"] = ("1440,900", "#v=" + json.dumps({"view": "board"}))
    if first_enum:
        shots["filtered"] = ("1440,900", "#v=" + json.dumps({"filters": {first_enum: ["__first__"]}}))
    for name, (size, hashv) in shots.items():
        w, h = size.split(",")
        png = project / "dashboard" / f"shot-{name}.png"
        if png.exists():
            png.unlink()
        _chrome([f"--screenshot={png}", f"file://{out}{hashv}"], png, width=int(w), height=int(h))
        size_b = png.stat().st_size if png.exists() else 0
        if size_b < 20_000:  # a blank "Loading…" frame is ~8 KB; retry once
            _chrome([f"--screenshot={png}", f"file://{out}{hashv}"], png, width=int(w), height=int(h))
            size_b = png.stat().st_size if png.exists() else 0
        print(f"{name}: {png} ({size_b} bytes){' — LOOK AT IT' if size_b else ' — FAILED'}")


def scaffold(project: Path, title: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    spec = {"kit": 1, "dataset_id": slug, "title": title, "id_field": "id", "display_field": "name",
            "fields": [{"key": "id", "label": "ID", "type": "id", "hidden": True},
                       {"key": "name", "label": "Name", "type": "text", "pin": True, "search": 3}],
            "default_sort": [{"field": "name", "dir": "asc"}], "default_view": "table", "views": ["table", "charts"],
            "pipeline": ["New", "Contacted", "Replied", "Qualified", "Won", "Lost"], "closed_stages": ["Won", "Lost"],
            "kpis": ["rows", "stages", "overdue", "coverage", "freshness", "duplicates"], "saved_views": []}
    (project / "dashboard.spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    (project / "adapter.py").write_text('''"""adapter.py — the only code a dataset needs. Read sources read-only."""
from pathlib import Path
import json


def load_rows(project_dir: Path):
    rows = json.loads((project_dir / "data" / "rows.json").read_text(encoding="utf-8"))
    meta = {"source": "data/rows.json", "pulled_min": None, "pulled_max": None, "notes": []}
    return rows, meta
''', encoding="utf-8")
    print(f"scaffolded {project}/dashboard.spec.json and adapter.py — fill the fields from the schema card, then `kit.py build`")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="kit.py")
    sub = ap.add_subparsers(dest="cmd")
    for name in ("build", "selftest", "screenshots", "verify"):
        s = sub.add_parser(name)
        s.add_argument("project", type=Path)
        if name in ("build", "verify"):
            s.add_argument("--quiet", action="store_true")
    ia = sub.add_parser("import-annotations")
    ia.add_argument("project", type=Path)
    ia.add_argument("path", type=Path)
    sub.add_parser("schema")
    nw = sub.add_parser("new")
    nw.add_argument("project", type=Path)
    nw.add_argument("--title", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "schema":
        print(SCHEMA)
        return 0
    if a.cmd == "new":
        scaffold(a.project.resolve(), a.title)
        return 0
    if a.cmd is None:
        ap.print_help()
        return 1
    project = a.project.resolve()
    if a.cmd == "build":
        build(project, a.quiet)
        return 0
    if a.cmd == "selftest":
        return selftest(project)
    if a.cmd == "screenshots":
        screenshots(project)
        return 0
    if a.cmd == "verify":
        build(project, a.quiet)
        rc = selftest(project)
        screenshots(project)
        return rc
    if a.cmd == "import-annotations":
        import_annotations(project, a.path)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
