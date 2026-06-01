import subprocess
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException

app = FastAPI()

PROJECT_ROOT = Path(__file__).resolve().parent
MAIN_FILE = PROJECT_ROOT / "main.py"

job_lock = threading.Lock()
job_running = False


def run_pipeline():
    global job_running

    try:
        subprocess.run(
            ["python", str(MAIN_FILE)],
            check=True,
        )
        print("✅ Fast Embedding Completed Successfully")

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")

    finally:
        job_running = False
        job_lock.release()


@app.post("/run-embedding")
def trigger_embedding():

    global job_running

    if not MAIN_FILE.exists():
        raise HTTPException(status_code=404, detail="main.py not found")

    if job_running:
        return {
            "status": "busy",
            "message": "Embedding already running",
        }

    if not job_lock.acquire(blocking=False):
        return {
            "status": "busy",
            "message": "Embedding already running",
        }

    job_running = True

    thread = threading.Thread(target=run_pipeline)
    thread.start()

    return {
        "status": "started",
        "message": "Embedding job started in background",
    }