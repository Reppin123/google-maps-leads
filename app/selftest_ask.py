"""selftest_ask.py: the Ask loop with a scripted model, on a throwaway project. No network, no key.
What it proves: the assistant can prepare but never run; a write through the SQL tool is refused;
tool results go back in one message; a draft campaign is only ever a draft."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

import ask
import runs
import store
from selftest import check, results, seed


class ScriptedModel:
    def __init__(self, turns):
        self.turns, self.calls = list(turns), []
        self.messages = self

    def create(self, **kw):
        self.calls.append({**kw, "messages": list(kw["messages"])})     # the history list keeps growing; keep what was sent
        return self.turns.pop(0)


def use(name, args, i):
    return NS(type="tool_use", id=f"tu_{i}", name=name, input=args)


def main() -> int:
    start = len(results)
    tmp = Path(tempfile.mkdtemp())
    os.environ["MAPS_LEADS_HOME"] = str(tmp / "shared-home")
    (tmp / "project.json").write_text('{"name": "Ask test", "country": "AU", "default_tz": "Australia/Sydney"}')
    store.use(tmp)
    conn = store.connect()
    seed(conn)
    store.migrate(conn)
    store.sync_contacts(conn)
    before = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    real_plan, runs.plan = runs.plan, lambda req: {"request": req, "places": 1, "points": 4, "est_points": 4, "hours": 0.1,
                                                   "phrases": req["phrases"], "biggest": [], "promises": []}
    print("the assistant prepares, the person runs")
    names = [t["name"] for t in ask.TOOLS]
    check(not [n for n in names if any(w in n for w in ("start", "launch", "send", "resume", "stop"))],
          f"no tool can start a search, launch a campaign or send an email ({', '.join(names)})")
    model = ScriptedModel([
        NS(stop_reason="tool_use", content=[NS(type="text", text="Let me plan that."),
           use("plan_search", {"phrases": ["plumbers", "gas fitter"], "country": "au", "near": "Perth", "sample": True}, 1),
           use("query_leads", {"sql": "DELETE FROM businesses"}, 2),
           use("query_leads", {"sql": "SELECT COUNT(*) n FROM businesses"}, 3)]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="I prepared a sample search. Press Start to run it.")])])
    out = ask.ask(conn, "c1", "find me plumbers around Perth", client=model)
    check(out["reply"].startswith("I prepared") and [c["type"] for c in out["cards"]] == ["plan"],
          "a search request comes back as a plan card, with the reply")
    check(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0] == 0 if conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='runs'").fetchone() else True, "planning started nothing")
    sent_back = model.calls[1]["messages"][-1]
    check(sent_back["role"] == "user" and len(sent_back["content"]) == 3, "all three tool results go back in one message")
    delete, count = sent_back["content"][1], json.loads(sent_back["content"][2]["content"])
    check(delete["is_error"] and conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0] == before
          and count["rows"][0]["n"] == before, "a DELETE through the query tool is refused and nothing is lost")
    check(model.calls[0]["model"] == "claude-opus-5" and "Ask test" in model.calls[0]["system"]
          and model.calls[1]["messages"][1]["role"] == "assistant", "the project is named to the model and history is kept in order")

    model = ScriptedModel([
        NS(stop_reason="tool_use", content=[use("draft_campaign", {"name": "Perth plumbers", "audience": {"trades": ["Plumbers"]},
           "emails": [{"versions": [{"subject": "Quick question, {short_name}", "body": "Hi {short_name|there}, A"},
                                    {"subject": "Missed calls?", "body": "Hi {short_name|there}, B"}]},
                      {"gap_days": 3, "versions": [{"subject": "", "body": "Following up."}]}]}, 1),
           use("propose_find_emails", {}, 2)]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="Drafted. Review it before launching.")])])
    out = ask.ask(conn, "c1", "draft a campaign for them", client=model)
    camp = conn.execute("SELECT * FROM out_campaigns ORDER BY id DESC LIMIT 1").fetchone()
    check(camp["status"] == "draft" and conn.execute("SELECT COUNT(*) FROM out_enrollments").fetchone()[0] == 0
          and out["cards"][0]["type"] == "campaign" and out["cards"][0]["inboxes"] > 0,
          f"a drafted campaign is a draft with nobody enrolled ({out['cards'][0]['inboxes']} inboxes match)")
    check(len(model.calls[0]["messages"]) == 5, "the second question carries the first exchange with it")
    runs.plan = real_plan
    failed = [label for ok, label in results[start:] if not ok]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
