import os
import json
from google import genai

MODEL = "gemini-1.5-flash"
TEXT_MODEL = "gemini-1.5-pro" 

SCHEMA = {
  "type": "object",
  "properties": {
    "merchant": {"type": "string"},
    "datetime": {"type": "string", "format": "date-time"},
    "currency": {"type": "string"},
    "subtotal": {"type": "number"},
    "tax": {"type": "number"},
    "tip": {"type": "number"},
    "total": {"type": "number"},
    "category": {"type": "string", "enum": [
      "food","transport","grocery","rent","utilities","shopping","health",
      "entertainment","coffee","other"
    ]},
    "line_items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {"desc":{"type":"string"}, "qty":{"type":"number"}, "price":{"type":"number"}},
        "required": ["desc","price"]
      }
    }
  },
  "required": ["merchant","total","category"]
}

MODEL = "gemini-1.5-flash-002"
TEXT_MODEL = "gemini-1.5-flash-002" 

PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-east5")

_genai_client = None
def genai_client():
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(
            vertexai=True,
            project=PROJECT,
            location=LOCATION,  # <-- critical
        )
    return _genai_client

def parse_receipt_gcs(gcs_uri: str) -> dict:
    prompt = (
        "Extract normalized expense fields from this receipt image. "
        "Return strictly valid JSON per the schema. Omit unknowns."
    )
    client = genai_client()
    resp = client.models.generate_content(
        model=MODEL,
        contents=[{"role": "user", "parts": [
            {"text": prompt},
            {"file_data": {"file_uri": gcs_uri}}
        ]}],
        config={
            "response_mime_type": "application/json",
            "response_schema": SCHEMA
        },
    )
    return getattr(resp, "parsed", {}) or {}

def parse_free_text(text: str) -> dict:
    client = genai_client()
    prompt = (
        "Extract merchant, subtotal, tax, tip, total, currency, datetime, category "
        f"from: {text}. Return JSON with those keys."
    )
    resp = client.models.generate_content(
        model=TEXT_MODEL,
        contents=[{"role": "user", "parts": [{"text": prompt}]}],
        config={"response_mime_type": "application/json"},
    )
    if hasattr(resp, "parsed") and isinstance(resp.parsed, dict):
        return resp.parsed
    try:
        return json.loads(getattr(resp, "text", "{}") or "{}")
    except Exception:
        return {"raw": getattr(resp, "text", "")}
