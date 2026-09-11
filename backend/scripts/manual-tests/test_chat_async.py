import json
import sys

# Read the request body
with open("chat_body.json", "r", encoding="utf-8") as f:
    body_data = json.load(f)

# Save to a file to confirm script ran
with open("python_ran.txt", "w", encoding="utf-8") as f:
    f.write("Script started\n")
    f.write(f"Query: {body_data['query']}\n")

import http.client
import time

start = time.time()
conn = http.client.HTTPConnection("localhost", 8002, timeout=180)
body = json.dumps(body_data)
headers = {"Content-Type": "application/json"}

try:
    conn.request("POST", "/api/v1/chat", body, headers)
    with open("python_ran.txt", "a", encoding="utf-8") as f:
        f.write(f"Request sent after {time.time()-start:.1f}s\n")
    
    resp = conn.getresponse()
    
    with open("python_ran.txt", "a", encoding="utf-8") as f:
        f.write(f"Response status: {resp.status} {resp.reason}\n")
    
    raw = resp.read().decode("utf-8")
    
    with open("python_ran.txt", "a", encoding="utf-8") as f:
        f.write(f"Response length: {len(raw)}\n")
    
    data = json.loads(raw)
    
    # Save full response
    with open("chat_response.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    with open("python_ran.txt", "a", encoding="utf-8") as f:
        f.write(f"SUCCESS: Answer length = {len(data.get('answer', ''))}\n")
        
except Exception as e:
    with open("python_ran.txt", "a", encoding="utf-8") as f:
        f.write(f"ERROR after {time.time()-start:.1f}s: {e}\n")