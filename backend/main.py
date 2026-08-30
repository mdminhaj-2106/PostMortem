"""FastAPI backend -- live orchestration + verification. See
.claude/plans/api-backend-orchestration-and-verification.md.

Usage:
    uvicorn main:app --reload
"""

import asyncio
import os

import psycopg2
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket
from fastapi.websockets import WebSocketDisconnect

import run_store
from orchestrator import run_pipeline

load_dotenv()

app = FastAPI(title="PS3 Live Pipeline API")

# One asyncio.Queue per in-flight run, so the WebSocket handler can await new events
# without polling. Cleared once the run finishes (queue.put(None) is the close signal).
_queues = {}


def _get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"])


@app.get("/episodes")
def list_episodes():
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT episode_id FROM episodes ORDER BY episode_id")
            return [{"episode_id": r[0]} for r in cur.fetchall()]
    finally:
        conn.close()


def _run_and_store(run_id, episode_id, use_llm, loop):
    # This function runs in FastAPI's threadpool (BackgroundTasks runs sync functions
    # via run_in_threadpool), not on the event loop thread -- asyncio.Queue isn't
    # thread-safe for a direct put_nowait from here, so every enqueue is dispatched
    # back onto the loop via call_soon_threadsafe instead.
    conn = _get_connection()
    queue = _queues.get(run_id)
    try:
        with conn.cursor() as cur:
            for event in run_pipeline(cur, episode_id, use_llm=use_llm):
                run_store.append_event(run_id, event)
                if queue is not None:
                    loop.call_soon_threadsafe(queue.put_nowait, event)
    finally:
        conn.close()
        if queue is not None:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # close signal
        _queues.pop(run_id, None)


@app.post("/runs")
async def start_run(episode_id: int, use_llm: bool, background_tasks: BackgroundTasks):
    # async, not sync: asyncio.get_running_loop() below needs to run on the actual
    # event loop thread. FastAPI runs a sync `def` endpoint in a worker thread via
    # anyio.to_thread.run_sync, where there is no running loop -- caught live as
    # RuntimeError: no running event loop.
    run_id = run_store.create_run(episode_id)
    _queues[run_id] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    background_tasks.add_task(_run_and_store, run_id, episode_id, use_llm, loop)
    return {"run_id": run_id}


@app.get("/runs/{run_id}")
def get_run(run_id: str):
    run = run_store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="unknown run_id")
    return run


@app.websocket("/ws/runs/{run_id}")
async def run_events(websocket: WebSocket, run_id: str):
    await websocket.accept()
    run = run_store.get_run(run_id)
    if run is None:
        await websocket.close(code=4404)
        return

    # Replay whatever already happened (handles a client connecting slightly late).
    for event in run["events"]:
        await websocket.send_json(event)
    if run["status"] == "finished":
        await websocket.close()
        return

    queue = _queues.get(run_id)
    if queue is None:
        await websocket.close()
        return
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        await websocket.close()
