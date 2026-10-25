#!/usr/bin/env python3
"""Run a resumable, direct-model evaluation without changing the serving system."""
import argparse
import concurrent.futures
import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SYSTEM_PROMPT = (
    "Bạn là trợ lý an ninh mạng. Trả lời bằng tiếng Việt, ngắn gọn (tối đa 200 từ), "
    "bám sát câu hỏi. Nêu giả định khi thiếu dữ liệu."
)


def load_config(path):
    values = {}
    for line in Path(path).read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def call_model(case, base_url, api_key, model, max_tokens, timeout, system_prompt=SYSTEM_PROMPT):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": case["prompt"]},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    started = time.monotonic()
    attempts = []
    for attempt in range(1, 4):
        request = urllib.request.Request(
            base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = json.load(response)
            choice = raw["choices"][0]
            content = choice["message"].get("content")
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty or non-text assistant content")
            return {
                **case,
                "transport_status": "ok",
                "response": content,
                "finish_reason": choice.get("finish_reason"),
                "model_reported": raw.get("model"),
                "usage": raw.get("usage"),
                "raw_response": raw,
                "attempts": attempts + [{"attempt": attempt, "status": "ok"}],
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        except urllib.error.HTTPError as error:
            # Do not store the server's arbitrary error body: it may contain credentials.
            attempts.append({"attempt": attempt, "status": "http_error", "http_status": error.code})
            retryable = error.code in (429, 500, 502, 503, 504)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            attempts.append({"attempt": attempt, "status": "connection_error", "error_type": type(error).__name__})
            retryable = True
        except (ValueError, KeyError, IndexError, TypeError) as error:
            attempts.append({"attempt": attempt, "status": "response_error", "error_type": type(error).__name__})
            retryable = False
        if not retryable or attempt == 3:
            break
        time.sleep(2 * attempt)
    return {
        **case,
        "transport_status": "error",
        "response": "",
        "attempts": attempts,
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Existing .env file; credentials are never written to results")
    parser.add_argument("--dataset", default="data/pentest_100.jsonl")
    parser.add_argument("--output", default="results/baseline.jsonl")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-tokens", type=int, default=1536)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--system-prompt-file", help="Optional neutral system prompt for this evaluation")
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 4 or args.max_tokens < 1 or args.timeout < 1:
        parser.error("concurrency must be 1..4; max-tokens and timeout must be positive")
    config = load_config(args.config)
    base_url, model = config["QWEN_BASE_URL"], config["QWEN_MODEL"]
    system_prompt = Path(args.system_prompt_file).read_text().strip() if args.system_prompt_file else SYSTEM_PROMPT
    if not system_prompt:
        parser.error("System prompt must not be empty")
    dataset = Path(args.dataset)
    cases = [json.loads(line) for line in dataset.read_text().splitlines() if line.strip()]
    assert len(cases) == 100 and len({c["id"] for c in cases}) == 100
    assert len({c["prompt"] for c in cases}) == 100
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = output.with_suffix(".meta.json")
    identity = {
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "base_url": base_url,
        "model_requested": model,
        "system_prompt": system_prompt,
        "temperature": 0,
        "max_tokens": args.max_tokens,
        "enable_thinking": False,
    }
    if metadata_path.exists():
        previous = json.loads(metadata_path.read_text())
        if any(previous.get(k) != v for k, v in identity.items()):
            parser.error("Dataset or request settings changed: select a new output path")
    else:
        if output.exists() and output.stat().st_size:
            parser.error("Existing results without metadata: select a new output path")
        metadata_path.write_text(json.dumps({
            **identity,
            "started_at_utc": datetime.now(timezone.utc).isoformat(),
            "dataset_path": str(dataset.resolve()),
            "concurrency": args.concurrency,
            "timeout_seconds": args.timeout,
            "mode": "direct LLM; no RAG; no external tools; authorized-lab prompts",
        }, ensure_ascii=False, indent=2) + "\n")
    existing = [json.loads(line) for line in output.read_text().splitlines()] if output.exists() else []
    done = {r["id"] for r in existing}
    assert len(done) == len(existing), "Duplicate result IDs"
    assert done <= {c["id"] for c in cases}, "Unknown result ID"
    pending = [c for c in cases if c["id"] not in done]
    if args.limit is not None:
        pending = pending[:args.limit]
    print(f"Model={model}; completed={len(done)}; pending={len(pending)}; concurrency={args.concurrency}", flush=True)
    with output.open("a") as handle, concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(call_model, c, base_url, config.get("QWEN_API_KEY", ""), model, args.max_tokens, args.timeout, system_prompt) for c in pending]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            handle.flush()
            done.add(result["id"])
            usage = result.get("usage") or {}
            print(f"{len(done)}/100 {result['id']} {result['transport_status']} finish={result.get('finish_reason')} tokens={usage.get('completion_tokens')} seconds={result['elapsed_seconds']}", flush=True)
    print(f"Saved {output}", flush=True)


if __name__ == "__main__":
    main()
