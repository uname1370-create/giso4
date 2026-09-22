import base64
import binascii
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from face.landmarks import build_target_mask
from processing.composite import composite_target
from processing.validation import validate_non_target_preservation

router = APIRouter()

class ProcessRequest(BaseModel):
    service: str = Field(min_length=1, max_length=32)
    original: str = Field(min_length=16)
    edited: str = Field(min_length=16)

class ProcessResponse(BaseModel):
    ok: bool
    service: str
    result: str
    maskCoverage: float
    preservationScore: float
    warnings: list[str]

def decode_data_uri(value: str) -> bytes:
    if "," not in value:
        raise ValueError("invalid data URI")
    header, payload = value.split(",", 1)
    if not header.startswith("data:image/") or ";base64" not in header:
        raise ValueError("unsupported image data URI")
    try:
        return base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid base64 image") from exc

def encode_png(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")

@router.post("/process", response_model=ProcessResponse)
def process(req: ProcessRequest) -> ProcessResponse:
    service = req.service.strip().lower()
    if service != "eyebrows":
        raise HTTPException(status_code=400, detail="Only the active eyebrows service is enabled in this version.")

    try:
        original = decode_data_uri(req.original)
        edited = decode_data_uri(req.edited)
        mask = build_target_mask(original, service)
        result_bytes, coverage = composite_target(original, edited, mask)
        score = validate_non_target_preservation(original, result_bytes, mask)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"vision processing failed: {type(exc).__name__}") from exc

    warnings: list[str] = []
    if coverage < 0.002:
        raise HTTPException(status_code=422, detail="Target region could not be detected reliably.")
    if coverage > 0.12:
        raise HTTPException(status_code=422, detail="Target mask is too large; refusing unsafe full-face compositing.")
    if score < 0.985:
        warnings.append("Non-target preservation score is below the preferred threshold.")

    return ProcessResponse(
        ok=True,
        service=service,
        result=encode_png(result_bytes),
        maskCoverage=coverage,
        preservationScore=score,
        warnings=warnings,
    )
