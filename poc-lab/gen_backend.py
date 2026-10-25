"""Backend sinh PoC qua API OpenAI-compatible (vLLM/unsloth serving, hoặc provider bất kỳ).

Dùng chung .env style với run_eval.py ở thư mục cha: cần QWEN_BASE_URL, QWEN_MODEL, QWEN_API_KEY
(tên biến giữ nguyên để tái dùng config có sẵn; trỏ tới endpoint nào cũng được).
"""
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


def load_config(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def extract_python_block(text: str) -> str:
    match = re.search(r"```python\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"```\s*(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def generate_poc(description: str, config: dict, system_prompt_template: str, timeout: int = 120) -> str:
    prompt = system_prompt_template.format(description=description)
    payload = {
        "model": config["QWEN_MODEL"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 2048,
        "stream": False,
    }
    request = urllib.request.Request(
        config["QWEN_BASE_URL"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + config.get("QWEN_API_KEY", ""),
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.load(response)
    content = raw["choices"][0]["message"]["content"]
    return extract_python_block(content)
