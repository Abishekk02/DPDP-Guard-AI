from bson import ObjectId
from app.database.mongodb import get_db
from app.config import settings


async def get_crawler_result(scan_id: str) -> dict | None:
    db = get_db()
    try:
        query = {"_id": ObjectId(scan_id)}
    except Exception:
        query = {"scan_id": scan_id}

    doc = await db[settings.CRAWLER_COLLECTION].find_one(query)
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc
