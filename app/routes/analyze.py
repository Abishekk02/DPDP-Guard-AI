from fastapi import APIRouter, HTTPException
from app.services.crawler_data import get_crawler_result
from app.services.classifier import classify_website

router = APIRouter()


@router.get("/analyze/{scan_id}")
async def analyze(scan_id: str):
    result = await get_crawler_result(scan_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"No crawler result found for scan_id: {scan_id}")

    try:
        classification = await classify_website(result)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=f"Classification failed: {e}")

    return {"scan_id": scan_id, "classification": classification, "data": result}
