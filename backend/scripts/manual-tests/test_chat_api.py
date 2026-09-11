import urllib.request
import json
import sys

body = json.dumps({"query": "你好", "top_k": 3}).encode("utf-8")
req = urllib.request.Request(
    "http://localhost:8002/api/v1/chat",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read().decode("utf-8"))
    print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)