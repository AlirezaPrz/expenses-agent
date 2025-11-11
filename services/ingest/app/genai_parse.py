from google import genai

# Shared JSON schema for normalized expenses
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
      "food","transport","grocery","rent","utilities","shopping","health","entertainment","coffee","other"
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

_client = genai.Client()
_MODEL = "gemini-2.0-flash"  # small & fast; great for the demo

def parse_receipt_gcs(gcs_uri: str) -> dict:
    prompt = (
      "Extract normalized expense fields from this receipt image. "
      "Return strictly valid JSON per the schema. "
      "If a field is missing on the receipt, omit it."
    )
    resp = _client.models.generate_content(
        model=_MODEL,
        contents=[{"role":"user","parts":[{"text": prompt}, {"file_data":{"file_uri": gcs_uri}}]}],
        config={"response_mime_type":"application/json", "response_schema": SCHEMA},
    )
    return resp.parsed  # dict

def parse_free_text(text: str) -> dict:
    prompt = (
      "Parse this free-form expense message into normalized fields. "
      "Handle info like amount, merchant, date/time words (today/yesterday), and category. "
      "Return strictly valid JSON per the schema."
    )
    resp = _client.models.generate_content(
        model=_MODEL,
        contents=[{"role":"user","parts":[{"text": prompt + "\n\nTEXT:\n" + text}]}],
        config={"response_mime_type":"application/json", "response_schema": SCHEMA},
    )
    return resp.parsed
