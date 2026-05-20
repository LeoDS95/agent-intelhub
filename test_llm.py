import os, sys, json, urllib.request
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()

key = os.environ["DEEPSEEK_API_KEY"]
base = os.environ["LLM_API_BASE"]

body = json.dumps({
    "model": "deepseek-ai/DeepSeek-V4-Flash",
    "messages": [
        {"role": "system", "content": "You are a professional analyst."},
        {"role": "user", "content": "Summarize in Chinese: 1. Xiaomi MiMo Reasoning Model announced 2. DeepSeek V4 Flash released 3. Node.js 26.0.0 out"}
    ],
    "max_tokens": 512,
    "temperature": 0.3,
}, ensure_ascii=True).encode("utf-8")

url = f"{base.rstrip('/')}/chat/completions"
req = urllib.request.Request(url, data=body, headers={
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
}, method="POST")

with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read().decode("utf-8"))
    print(data["choices"][0]["message"]["content"])
    print("---")
    print(f"Tokens: {data['usage']['total_tokens']}")
