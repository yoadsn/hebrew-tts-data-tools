import uvicorn

from numeric_pairs.web.app import pipeline_store

if __name__ == "__main__":
    pipeline_store.resume_pending_monitors()
    uvicorn.run("numeric_pairs.web.app:app", host="127.0.0.1", port=8766)
