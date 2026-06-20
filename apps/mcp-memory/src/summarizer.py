import json
import re
import urllib.request
import urllib.error

KOBOLD_API = "http://localhost:11434/v1/chat/completions"
MAX_OUTPUT_TOKENS = 60
TIMEOUT = 30


def summarize(text: str, category: str = "context") -> str:
    if not text or len(text) < 60:
        return text

    if len(text) > 2000:
        text = text[:2000] + " [...]"

    system_prompt = (
        "Summarize concisely. Output ONLY 1-2 sentences with the key "
        "facts, entities, numbers, and decisions. No explanations."
    )

    payload = {
        "model": "koboldcpp",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "max_tokens": MAX_OUTPUT_TOKENS,
        "temperature": 0.2,
        "top_p": 0.9,
    }

    req = urllib.request.Request(
        KOBOLD_API,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read().decode())
            summary = result["choices"][0]["message"]["content"].strip()
            summary = re.sub(r"<think>.*?</think>", "", summary, flags=re.DOTALL).strip()
            summary = re.sub(r"^(Here['´]s a summary:|Summary:|In summary:)\s*", "", summary, flags=re.IGNORECASE)
            if summary:
                return summary
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as e:
        print(f"[summarizer] Error: {e}", file=__import__('sys').stderr)

    return text
