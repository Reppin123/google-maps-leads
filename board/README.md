# board/ : the leads board

Each project describes its board in `dashboard.spec.json` (fields, filters, charts, pipeline stages,
`auto_stages`) and `adapter.py` (`load_rows()`, reads the database read-only). `board/` is a self-contained module: `kit.py` (build, verify), `template.html` (the page),
`vendor/` (libraries, see `vendor/THIRD_PARTY.md`), and the `default_*` files every new project starts with.

- **In the app** (`app.py serve`, the Leads tab): built from the database on each change, stages and
  notes saved to `board_annotations` in the project database, "Email these" turns the filtered or
  selected leads into a draft campaign, and sending moves leads forward on its own (queued,
  contacted, replied). A stage set by hand is never overridden by an older email event, and a
  closed stage such as Won is never reopened.
- **As a file to hand over**: `uv run --script ~/maps-leads/board/kit.py build .` writes
  `dashboard/index.html`, which works with no server. `verify .` runs its self-test and screenshots.

## Commands

```
uv run --script ~/maps-leads/board/kit.py build .      # schema card + dashboard/index.html
uv run --script ~/maps-leads/board/kit.py verify .     # build + self-test at 1440 and 500 px + screenshots
uv run --script ~/maps-leads/board/kit.py schema       # the spec contract
```
