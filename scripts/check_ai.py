"""Manual minimal free-tier connection check; never prints keys or raw replies."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from newsbrief.ai import Gemini
from newsbrief.config import MODEL

client = Gemini(max_calls=3)
schema = {"type": "OBJECT", "properties": {"ok": {"type": "BOOLEAN"}}, "required": ["ok"]}
result = client.request("Respond with the JSON object {\"ok\":true}.", [], schema)
print(f"Model: {MODEL}; requests: {client.calls}; status: {client.reason or 'ok'}")
if client.last_error:
    print("Sanitized API diagnostic: " + client.last_error)
if result == {"ok": True}:
    print("Minimal structured generation succeeded")
else:
    print("Minimal generation failed")
    sys.exit(1)
