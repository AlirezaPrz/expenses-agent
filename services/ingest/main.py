from fastapi import FastAPI, UploadFile, Form
from google.cloud import storage, firestore
from dateutil import parser as dateparser
import uuid, datetime

from app.config import BUCKET, PROJECT_ID, DEFAULT_USER, DEFAULT_CURRENCY
from app.genai_parse import parse_receipt_gcs, parse_free_text
from app.reporting import sum_by_category_firestore

app = FastAPI(title="Expenses Ingest API")

storage_client = storage.Client()
firestore_client = firestore.Client(project=PROJECT_ID)

from fastapi.responses import PlainTextResponse

@app.get("/", response_class=PlainTextResponse)
def root():
    return "expenses-ingest alive"

@app.get("/health", response_class=PlainTextResponse)
def health_text():
    return "ok"

@app.on_event("startup")
async def log_routes():
    print("ROUTES:", [r.path for r in app.routes])


def _save_tx(parsed: dict, source: str, raw_uri: str = ""):
    # Normalize and fill safe defaults
    ts = parsed.get("datetime")
    ts_dt = dateparser.parse(ts) if ts else datetime.datetime.utcnow()
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
        "raw_uri": raw_uri
    }
    ref = (firestore_client.collection("users").document(DEFAULT_USER)
                          .collection("transactions").document(str(uuid.uuid4())))
    ref.set(doc)
    doc["id"] = ref.id
    return doc

@app.get("/health")
def health():
    return {"ok": True, "project": PROJECT_ID}

@app.post("/text")
async def add_text_expense(text: str = Form(...)):
    parsed = parse_free_text(text)
    saved = _save_tx(parsed, source="text")
    return {"saved": True, "parsed": parsed, "doc": saved}

@app.post("/upload-receipt")
async def upload_receipt(file: UploadFile):
    # 1) Upload to GCS
    bucket = storage_client.bucket(BUCKET)
    blob_name = f"receipts/{uuid.uuid4()}_{file.filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file.file, content_type=file.content_type)
    gcs_uri = f"gs://{BUCKET}/{blob_name}"

    # 2) Parse via Gemini Structured Output
    parsed = parse_receipt_gcs(gcs_uri)

    # 3) Save to Firestore
    saved = _save_tx(parsed, source="receipt", raw_uri=gcs_uri)
    return {"uploaded": True, "gcs": gcs_uri, "parsed": parsed, "doc": saved}

@app.get("/report")
def report(days: int = 30):
    # Simple Firestore aggregation (client-side)
    col = (firestore_client.collection("users").document(DEFAULT_USER)
                           .collection("transactions"))
    docs = list(col.stream())
    buckets = sum_by_category_firestore(docs, days=days)
    return {"days": days, "by_category": buckets}
