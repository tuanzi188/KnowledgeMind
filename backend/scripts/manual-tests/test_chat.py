import urllib.request
import json

body = json.dumps({"query": "你好", "top_k": 3}).encode("utf-8")
req = urllib.request.Request(
    "http://localhost:8002/api/v1/chat",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    resp = urllib.request.urlopen(req, timeout=60)
    print(resp.read().decode("utf-8"))
except Exception as e:
    print(f"ERROR: {e}")