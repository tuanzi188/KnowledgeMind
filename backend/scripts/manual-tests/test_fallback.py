import requests
import json

body = {"query": "你好", "conversation_id": "test_fix", "use_fallback": True}
try:
    resp = requests.post("http://localhost:8002/api/v1/chat", json=body, timeout=45)
    print(f"Status: {resp.status_code}")
    data = resp.json()
    print(f"is_fallback: {data.get('is_fallback')}")
    print(f"answer: {data.get('answer', '')[:200]}")
except Exception as e:
    print(f"Error: {e}")