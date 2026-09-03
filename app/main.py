"""FastAPI entrypoint for the Vera Decision & Message Engine."""

from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(
    title="Vera Decision Engine",
    description="Deterministic message intelligence service for magicpin AI Challenge",
    version="1.0.0",
)

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False)
