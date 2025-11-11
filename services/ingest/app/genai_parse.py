# All heavy deps are imported + created lazily so startup never fails.

import os

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

_MODEL = "gemini-2.0-flash"

def _client():
    # Import here to avoid module import-time failures.
    from google import genai
    # Pull project/location from env (Cloud Run sets GOOGLE_CLOUD_PROJECT; we set region).
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
    return genai.Client(project=project, vertexai_location=location)

def parse_receipt_gcs(gcs_uri: str) -> dict:
    prompt = ("Extract normalized expense fields from this receipt image. "
              "Return strictly valid JSON per the schema. Omit unknowns.")
    resp = _client().models.generate_content(
        model=_MODEL,
        contents=[{"role":"user","parts":[{"text": prompt}, {"file_data":{"file_uri": gcs_uri}}]}],
        config={"response_mime_type":"application/json", "response_schema": SCHEMA},
    )
    return resp.parsed  # dict

def parse_free_text(text: str) -> dict:
    prompt = ("Parse this free-form expense message into normalized fields per the schema. "
              "Infer a sensible category; use ISO datetime if possible.")
    resp = _client().models.generate_content(
        model=_MODEL,
        contents=[{"role":"user","parts":[{"text": prompt + "\n\nTEXT:\n" + text}]}],
        config={"response_mime_type":"application/json", "response_schema": SCHEMA},
    )
    return resp.parsed
