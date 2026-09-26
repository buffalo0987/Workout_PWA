import urllib.request, json
payload = {
    "model": "qwen3:14b",
    "prompt": "I am currently 145 pounds and would like to gain weight and get stronger. Could you make a push pull legs routine for me?",
    "system": "Return ONLY valid JSON in this exact format:\n{\"message\": \"...\", \"routines_to_create\": [{\"title\": \"...\", \"exercises\": [{\"name\": \"Bench Press\", \"target_sets\": 3}]}]}",
    "stream": False,
    "format": "json",
    "options": {"temperature": 0.2}
}
req = urllib.request.Request("https://ollama.my-home-ok.duckdns.org/api/generate", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
resp = urllib.request.urlopen(req, timeout=120)
print(resp.read().decode("utf-8"))
