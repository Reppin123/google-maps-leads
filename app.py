# /// script
# requires-python = ">=3.9"
# dependencies = ["dnspython", "requests==2.32.3", "anthropic"]
# ///
"""
app.py: the one entry point for working on a project.

  uv run --script app.py new-project ~/maps-leads-projects/acme --name "Acme leads" --country AU --tz Australia/Sydney
  uv run --script app.py serve                            # the app, http://127.0.0.1:8770 (home screen, every project)
  uv run --script app.py sync     --project <folder>     # refresh contacts after new enrichment
  uv run --script app.py tick     --project <folder>     # read the mailbox, then send at most one email
  uv run --script app.py schedule on|off --project <folder>
  uv run --script app.py selftest                        # whole campaign on a throwaway project

--project can be left out when the command is run from inside the project folder.
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
sys.path[:0] = [str(REPO / d) for d in ("app", "outreach", "leads", "board", "scrape")]
import mailer  # noqa: E402
import project as projects  # noqa: E402
import store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["serve", "sync", "tick", "schedule", "selftest", "new-project"])
    ap.add_argument("arg", nargs="?")
    ap.add_argument("--project")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--name", default="")
    ap.add_argument("--country", default="")
    ap.add_argument("--tz", default="UTC")
    a = ap.parse_args()

    if a.command == "selftest":
        import selftest
        import selftest_ask
        import selftest_delivery
        failed = selftest.main() + selftest_delivery.main() + selftest_ask.main()
        print(f"\nall checks: {sum(ok for ok, _ in selftest.results)}/{len(selftest.results)} passed")
        return 1 if failed else 0
    if a.command == "new-project":
        print("Created", projects.create(a.arg or a.project, a.name, a.country, a.tz))
        return 0
    if a.command == "serve":                       # no project needed: the home screen lists them all
        import server
        here = a.project or ("." if Path("project.json").exists() else None)
        server.serve(a.port, projects.resolve(here) if here else None)
        return 0
    store.use(projects.resolve(a.project))
    if a.command == "schedule":
        print(mailer.schedule(a.arg == "on"))
    else:
        conn = store.connect()
        store.migrate(conn)
        if a.command == "sync":
            print(json.dumps(store.sync_contacts(conn), indent=1))
        else:
            print(store.iso(store.now_utc()), json.dumps(mailer.tick(conn)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
