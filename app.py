"""Standalone detector service called by ChainGuard."""
import logging
import os
import secrets

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from detector import detect
from schema import AddressContext, DetectionResult

logger = logging.getLogger(__name__)
app = FastAPI(title="ChainGuard Detector API", version="1.0.0")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def authenticate(api_key: str | None = Depends(api_key_header)) -> None:
    expected = os.environ.get("DETECTOR_API_KEY")
    if expected and (not api_key or not secrets.compare_digest(
        api_key.encode("utf-8"), expected.encode("utf-8")
    )):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


@app.get("/health")
def health():
    """Process liveness; does not execute the detector."""
    return {"status": "ok"}


@app.post("/detect", response_model=DetectionResult, response_model_exclude_none=True,
          dependencies=[Depends(authenticate)])
def run_detection(context: AddressContext) -> DetectionResult:
    try:
        return DetectionResult.model_validate(detect(context))
    except Exception:
        logger.exception("Detector execution or output validation failed")
        raise HTTPException(status_code=500, detail="Detector failed to produce a valid result") from None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"),
                port=int(os.environ.get("PORT", "9000")))
