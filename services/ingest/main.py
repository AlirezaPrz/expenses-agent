import os
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi import FastAPI, UploadFile, Form
from google.cloud import storage, firestore
from dateutil import parser as dateparser
import uuid, datetime
from app.config import BUCKET, PROJECT_ID, DEFAULT_USER, DEFAULT_CURRENCY
from app.genai_parse import parse_receipt_gcs, parse_free_text
from app.reporting import sum_by_category_firestore
from pydantic import BaseModel

app = FastAPI(title="Expenses Ingest API")

storage_client = storage.Client()
firestore_client = firestore.Client(project=PROJECT_ID)

@app.get("/")
def root():
    return "expenses-ingest alive"

@app.get("/healthz")
def health_json():
    return {"ok": True, "project": PROJECT_ID, "bucket_set": bool(BUCKET)}

def _to_utc(dt: datetime.datetime) -> datetime.datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)

def _save_tx(parsed: dict, source: str, raw_uri: str = ""):
    # Normalize and fill safe defaults
    ts = parsed.get("datetime")
    ts_dt = _to_utc(dateparser.parse(ts)) if ts else datetime.datetime.now(datetime.timezone.utc)
    doc = {
        "user_id": DEFAULT_USER,
        "ts": ts_dt,
        "merchant": parsed.get("merchant") or "unknown",
        "currency": parsed.get("currency") or DEFAULT_CURRENCY,
        "subtotal": float(parsed.get("subtotal") or 0.0),
        "tax": float(parsed.get("tax") or 0.0),
        "tip": float(parsed.get("tip") or 0.0),
        "total": float(parsed.get("total") or 0.0),
        "category": parsed.get("category") or "other",
        "source": source,
        "raw_uri": raw_uri,
    }
    ref = (firestore_client.collection("users").document(DEFAULT_USER)
                          .collection("transactions").document(str(uuid.uuid4())))
    ref.set(doc)
    doc["id"] = ref.id
    return doc

class TextIn(BaseModel):
    text: str

@app.post("/text-json")
async def add_text_json(payload: TextIn):
    parsed = parse_free_text(payload.text)
    saved = _save_tx(parsed, source="text")
    return {"saved": True, "parsed": parsed, "doc": saved}

@app.post("/upload-receipt")
async def upload_receipt(file: UploadFile):
    bucket = storage_client.bucket(BUCKET)
    blob_name = f"receipts/{uuid.uuid4()}_{file.filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file.file, content_type=file.content_type)
    gcs_uri = f"gs://{BUCKET}/{blob_name}"
    parsed = parse_receipt_gcs(gcs_uri, mime_type=file.content_type or "image/jpeg")
    saved = _save_tx(parsed, source="receipt", raw_uri=gcs_uri)
    return {"uploaded": True, "gcs": gcs_uri, "parsed": parsed, "doc": saved}

@app.get("/report")
def report(days: int = 30):
    col = (firestore_client.collection("users").document(DEFAULT_USER)
                           .collection("transactions"))
    docs = list(col.stream())
    buckets = sum_by_category_firestore(docs, days=days)
    return {"days": days, "by_category": buckets}
