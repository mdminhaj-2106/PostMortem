"""Backend self-check -- offline invariants for orchestrator/verification/run_store,
plus one live run of the real backend app (FastAPI TestClient) against episode 15
through the WebSocket. See
.claude/plans/api-backend-orchestration-and-verification.md.

Run: .venv/bin/python test_backend.py
"""

import os
from types import SimpleNamespace

from dotenv import load_dotenv

import run_store
from verification import _match_event, _overlap_days, score_run

# --- offline ---


def test_overlap_days():
    assert _overlap_days(10, 20, 15, 25) == 5
    assert _overlap_days(10, 20, 25, 30) == 0


def test_match_event_picks_the_most_overlapping_and_none_when_no_overlap():
    events = [("marketing_cut", 40, 60), ("inventory_shortage", 100, 110)]
    assert _match_event(45, 55, events) == "marketing_cut"
    assert _match_event(200, 210, events) is None


def test_score_run_no_hit_when_no_matching_event():
    stage3_result = SimpleNamespace(window_start_day_offset=200, window_end_day_offset=210)
    stage7_result = SimpleNamespace(
        abstained=False,
        hypotheses=[SimpleNamespace(hypothesis_id="h1", member_causes=["marketing_cut"], rank=1)],
    )

    class _FakeCursor:
        def execute(self, *a):
            pass

        def fetchall(self):
            return [("marketing_cut", 40, 60)]

    result = score_run(_FakeCursor(), 1, stage3_result, stage7_result)
    assert result["matched_event_type"] is None
    assert result["top1_hit"] is None and result["top3_hit"] is None
    assert result["counterfactual_mae"] is None


def test_score_run_top1_hit_when_ranked_first_matches():
    stage3_result = SimpleNamespace(window_start_day_offset=45, window_end_day_offset=55)
    stage7_result = SimpleNamespace(
        abstained=False,
        hypotheses=[
            SimpleNamespace(hypothesis_id="h2", member_causes=["competitor_launch"], rank=2),
            SimpleNamespace(hypothesis_id="h1", member_causes=["marketing_cut"], rank=1),
        ],
    )

    class _FakeCursor:
        def execute(self, *a):
            pass

        def fetchall(self):
            return [("marketing_cut", 40, 60)]

    result = score_run(_FakeCursor(), 1, stage3_result, stage7_result)
    assert result["matched_event_type"] == "marketing_cut"
    assert result["top1_hit"] is True
    assert result["top3_hit"] is True


def test_run_store_roundtrip():
    run_id = run_store.create_run(15)
    assert run_store.get_run(run_id)["status"] == "running"
    run_store.append_event(run_id, {"stage": "stage3", "status": "completed", "summary": {}})
    assert run_store.get_run(run_id)["status"] == "running"
    run_store.append_event(run_id, {"stage": "verification", "status": "completed", "summary": {}})
    run = run_store.get_run(run_id)
    assert run["status"] == "finished"
    assert len(run["events"]) == 2
    assert run_store.get_run("no-such-id") is None


def test_run_store_no_cluster_finishes_the_run():
    run_id = run_store.create_run(2)
    run_store.append_event(run_id, {"stage": "stage3", "status": "no_cluster", "summary": {}})
    assert run_store.get_run(run_id)["status"] == "finished"


# --- live: the real app, episode 15, over a real WebSocket ---


def test_live_run_episode_15():
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)

    episodes = client.get("/episodes").json()
    assert any(e["episode_id"] == 15 for e in episodes), "expected episode 15 to be listed"

    run_id = client.post("/runs", params={"episode_id": 15, "use_llm": True}).json()["run_id"]

    events = []
    with client.websocket_connect(f"/ws/runs/{run_id}") as ws:
        while True:
            event = ws.receive_json()
            events.append(event)
            if event["stage"] == "verification" or event["status"] == "no_cluster":
                break

    stages_seen = [e["stage"] for e in events]
    print(f"\nlive run: episode 15, stages={stages_seen}")
    assert "verification" in stages_seen, "expected a full run to reach verification"

    verification_event = events[-1]
    print(f"  verification: {verification_event['summary']}")

    narration_event = next(e for e in events if e["stage"] == "stage10_11")
    for persona, data in narration_event["summary"].items():
        assert data["narrative"], f"{persona} narrative was empty"
        assert data["usage"]["input_tokens"] > 0

    # GET /runs/{run_id} after the socket has already closed must return the full transcript
    replay = client.get(f"/runs/{run_id}").json()
    assert replay["status"] == "finished"
    assert len(replay["events"]) == len(events)


if __name__ == "__main__":
    test_overlap_days()
    test_match_event_picks_the_most_overlapping_and_none_when_no_overlap()
    test_score_run_no_hit_when_no_matching_event()
    test_score_run_top1_hit_when_ranked_first_matches()
    test_run_store_roundtrip()
    test_run_store_no_cluster_finishes_the_run()

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL not set -- offline checks passed, live run needs it.")
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise SystemExit("GEMINI_API_KEY not set -- offline checks passed, live run needs it.")
    test_live_run_episode_15()
    print("OK")
