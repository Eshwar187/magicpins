"""Bot entrypoint conforming to challenge brief convention (uvicorn bot:app)."""

from app.main import app

__all__ = ["app"]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bot:app", host="0.0.0.0", port=8080, reload=False)
