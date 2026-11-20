import uvicorn

if __name__ == "__main__":
    uvicorn.run("numeric_pairs.web.app:app", host="127.0.0.1", port=8766)
