import os
from app.genai_parse import list_models as gp_list_models, LOCATION
from fastapi.responses import PlainTextResponse, JSONResponse
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

@app.get("/env", response_class=PlainTextResponse)
def env_dump():
    proj = os.getenv("GOOGLE_CLOUD_PROJECT")
    loc = os.getenv("GOOGLE_CLOUD_LOCATION")
    return f"GOOGLE_CLOUD_PROJECT={proj}\nGOOGLE_CLOUD_LOCATION={loc}"

@app.get("/whoami", response_class=PlainTextResponse)
def whoami():
    import google.auth
    creds, proj = google.auth.default()
    return f"SA={getattr(creds, 'service_account_email', 'unknown')}\nPROJECT={proj}"

@app.get("/models")
def models():
    try:
        return {"location": LOCATION, "models": gp_list_models()}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/", response_class=PlainTextResponse)
def root():
    return "expenses-ingest alive"

@app.get("/healthz")
def health_json():
    return {"ok": True, "project": PROJECT_ID, "bucket_set": bool(BUCKET)}

@app.on_event("startup")
async def log_routes():
    print("ROUTES:", [r.path for r in app.routes])

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

# --- Text (form) ---
@app.post("/text")
async def add_text_expense(text: str = Form(...)):
    parsed = parse_free_text(text)
    saved = _save_tx(parsed, source="text")
    return {"saved": True, "parsed": parsed, "doc": saved}

# --- Text (JSON) -- optional but convenient ---
from pydantic import BaseModel
class TextIn(BaseModel):
    text: str

@app.post("/text-json")
async def add_text_json(payload: TextIn):
    parsed = parse_free_text(payload.text)
    saved = _save_tx(parsed, source="text")
    return {"saved": True, "parsed": parsed, "doc": saved}

# --- Receipt upload ---
@app.post("/upload-receipt")
async def upload_receipt(file: UploadFile):
    bucket = storage_client.bucket(BUCKET)
    blob_name = f"receipts/{uuid.uuid4()}_{file.filename}"
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file.file, content_type=file.content_type)
    gcs_uri = f"gs://{BUCKET}/{blob_name}"

    # NEW: pass mime_type
    parsed = parse_receipt_gcs(gcs_uri, mime_type=file.content_type or "image/jpeg")
    saved = _save_tx(parsed, source="receipt", raw_uri=gcs_uri)
    return {"uploaded": True, "gcs": gcs_uri, "parsed": parsed, "doc": saved}

# --- Report ---
@app.get("/report")
def report(days: int = 30):
    col = (firestore_client.collection("users").document(DEFAULT_USER)
                           .collection("transactions"))
    docs = list(col.stream())
    buckets = sum_by_category_firestore(docs, days=days)
    return {"days": days, "by_category": buckets}
