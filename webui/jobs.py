"""jobs.py — tiny in-memory background job runner for the local web UI.

Transcription, caption generation and publishing can take seconds to minutes.
We run them in a daemon thread and let the frontend poll /api/job/<id>.
Single-user local tool, so an in-memory dict is plenty — no Celery/Redis.
"""
import threading
import traceback
import uuid

_jobs = {}
_lock = threading.Lock()


def _set(job_id, **fields):
    with _lock:
        _jobs[job_id].update(fields)


def start(fn, *args, **kwargs):
    """Run fn(*args, progress=callable, **kwargs) in a background thread.

    fn receives a `progress(message)` callback it can call to update status.
    Whatever fn returns becomes the job's `result`.
    Returns the job_id.
    """
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {"status": "running", "progress": "", "result": None, "error": None}

    def progress(message):
        _set(job_id, progress=message)

    def run():
        try:
            result = fn(*args, progress=progress, **kwargs)
            _set(job_id, status="done", result=result, progress="")
        except Exception as e:
            _set(job_id, status="error", error=str(e))
            traceback.print_exc()

    threading.Thread(target=run, daemon=True).start()
    return job_id


def get(job_id):
    with _lock:
        return dict(_jobs.get(job_id, {"status": "unknown", "error": "no such job"}))
