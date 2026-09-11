import http.client
import json
import time

start = time.time()
conn = http.client.HTTPConnection("localhost", 8002, timeout=120)
body = json.dumps({"query": "你好，请介绍一下你自己", "top_k": 3})
headers = {"Content-Type": "application/json"}
try:
    conn.request("POST", "/api/v1/chat", body, headers)
    resp = conn.getresponse()
    data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.time() - start
    print(f"耗时: {elapsed:.1f}秒")
    print(json.dumps(data, ensure_ascii=False, indent=2))
except Exception as e:
    elapsed = time.time() - start
    print(f"失败 (耗时{elapsed:.1f}秒): {e}")