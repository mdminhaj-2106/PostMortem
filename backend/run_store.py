"""In-memory run transcript store. No DB table -- a run's event history doesn't need
to outlive the process for this slice (stated in the design report's Scope/Out, not a
silent gap: a backend restart loses all run history).
"""

import uuid

_runs = {}


def create_run(episode_id):
    run_id = str(uuid.uuid4())
    _runs[run_id] = {"episode_id": episode_id, "status": "running", "events": []}
    return run_id


def append_event(run_id, event):
    """The generator's last event is either stage3's no_cluster early-terminate or
    the final verification event -- either one closes the run."""
    run = _runs[run_id]
    run["events"].append(event)
    if event["stage"] == "verification" or event["status"] == "no_cluster":
        run["status"] = "finished"


def get_run(run_id):
    return _runs.get(run_id)
