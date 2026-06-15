#!/usr/bin/env python3
"""Generate a textless brand backdrop PNG via the OpenAI image API (gpt-image-2).
Key from env OPENAI_API_KEY (never hard-coded). Text is composited later as
crisp SVG — image models garble letters, so prompts must request NO text.
Usage: OPENAI_API_KEY=... gen_image.py "<prompt>" <out.png> [size] [model]
"""
import base64, json, os, sys, urllib.request

MODEL = os.environ.get("TROVEX_IMAGE_MODEL", "gpt-image-2")

def main():
    prompt, out = sys.argv[1], sys.argv[2]
    size = sys.argv[3] if len(sys.argv) > 3 else "1536x1024"
    model = sys.argv[4] if len(sys.argv) > 4 else MODEL
    key = os.environ["OPENAI_API_KEY"]
    body = json.dumps({
        "model": model, "prompt": prompt, "size": size,
        "n": 1, "quality": "high", "background": "opaque",
    }).encode()
    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations", data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        sys.stderr.write(e.read().decode()[:500] + "\n")
        raise
    b64 = data["data"][0]["b64_json"]
    with open(out, "wb") as f:
        f.write(base64.b64decode(b64))
    print(f"wrote {out} ({size}, {model})")

if __name__ == "__main__":
    main()
