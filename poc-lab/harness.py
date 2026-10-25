#!/usr/bin/env python3
"""Harness TC1: cho từng CVE trong cve_set.jsonl, AI sinh PoC toàn trình từ mô tả,
chạy PoC trong secai-kali-executor nhắm vào target Docker cô lập, chấm pass/fail
bằng oracle riêng của CVE, tổng hợp kết quả theo tier (easy/medium/excellent).

Dùng:
    python3 harness.py --config /path/to/.env [--dry-run] [--only demo-cmdi-001]

.env cần: QWEN_BASE_URL, QWEN_MODEL, QWEN_API_KEY (endpoint OpenAI-compatible bất kỳ,
ví dụ vLLM serving model fine-tune bằng unsloth).

--dry-run: không gọi AI, dùng PoC đã có sẵn trong poc_generated/<id>.py (để test riêng
pipeline target+oracle mà không tốn lệnh gọi model).
"""
import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import gen_backend

ROOT = Path(__file__).resolve().parent
EXECUTOR_RUN = ROOT.parent.parent / "secai-kali-executor" / "run.sh"
SYSTEM_PROMPT = (ROOT / "prompts" / "system_prompt.txt").read_text()


def load_cve_set(path: Path):
    cases = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def load_oracle(module_name: str):
    path = ROOT / "oracles" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_cmd(cmd, **kwargs):
    print(f"$ {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def bring_up_target(case_id: str):
    compose_file = ROOT / "targets" / case_id / "docker-compose.yml"
    project = f"poclab-{case_id}"
    run_cmd(["docker", "compose", "-p", project, "-f", str(compose_file), "up", "-d", "--build"])
    # chờ healthcheck
    for _ in range(30):
        status = run_cmd(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", f"{project}-target"]
        ).stdout.strip()
        if status == "healthy":
            break
        time.sleep(1)
    else:
        print(f"[!] target {case_id} không healthy sau 30s, tiếp tục thử chạy PoC")
    return project


def tear_down_target(case_id: str):
    compose_file = ROOT / "targets" / case_id / "docker-compose.yml"
    project = f"poclab-{case_id}"
    run_cmd(["docker", "compose", "-p", project, "-f", str(compose_file), "down", "-v"])


def run_poc_in_executor(case_id: str, project: str, port: int):
    poc_path = ROOT / "poc_generated" / f"{case_id}.py"
    network = f"{project}_default"
    env = {
        "NET": network,
        "MOUNTS": f"-v {poc_path}:/work/poc.py:ro",
        "EXEC_TIMEOUT": "60",
    }
    cmd = [str(EXECUTOR_RUN), "raw", "python3", "/work/poc.py", "--target", f"target:{port}"]
    import os

    full_env = {**os.environ, **env}
    print(f"$ NET={network} MOUNTS=... {' '.join(cmd)}")
    return subprocess.run(cmd, capture_output=True, text=True, env=full_env, timeout=90)


def process_case(case: dict, config: dict | None, dry_run: bool):
    case_id = case["id"]
    poc_path = ROOT / "poc_generated" / f"{case_id}.py"

    if not dry_run:
        code = gen_backend.generate_poc(case["description_for_ai"], config, SYSTEM_PROMPT)
        poc_path.write_text(code)
    elif not poc_path.exists():
        return {**case, "status": "error", "error": "dry-run nhưng chưa có PoC sẵn trong poc_generated/"}

    project = bring_up_target(case_id)
    try:
        result = run_poc_in_executor(case_id, project, case["target_port"])
    except subprocess.TimeoutExpired as exc:
        tear_down_target(case_id)
        return {**case, "status": "error", "error": f"timeout: {exc}"}
    tear_down_target(case_id)

    oracle = load_oracle(case["oracle_module"])
    passed = oracle.check(result.stdout, result.stderr, result.returncode)

    return {
        **case,
        "status": "pass" if passed else "fail",
        "poc_path": str(poc_path),
        "stdout_excerpt": result.stdout[-2000:],
        "stderr_excerpt": result.stderr[-2000:],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="path to .env với QWEN_BASE_URL/QWEN_MODEL/QWEN_API_KEY")
    parser.add_argument("--cve-set", default=str(ROOT / "cve_set.jsonl"))
    parser.add_argument("--output", default=str(ROOT / "results" / "run.jsonl"))
    parser.add_argument("--only", help="chỉ chạy 1 id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.config:
        sys.exit("cần --config (.env) khi không ở --dry-run")

    config = gen_backend.load_config(args.config) if args.config else None
    cases = load_cve_set(Path(args.cve_set))
    if args.only:
        cases = [c for c in cases if c["id"] == args.only]

    results = []
    for case in cases:
        print(f"=== {case['id']} (tier={case['tier']}) ===")
        try:
            record = process_case(case, config, args.dry_run)
        except Exception as exc:  # noqa: BLE001 - ghi lại lỗi, không chặn case khác
            record = {**case, "status": "error", "error": str(exc)}
        print(f"-> {record['status']}")
        results.append(record)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_tier = {}
    for r in results:
        by_tier.setdefault(r["tier"], {"pass": 0, "total": 0})
        by_tier[r["tier"]]["total"] += 1
        if r["status"] == "pass":
            by_tier[r["tier"]]["pass"] += 1

    print("\n=== Tổng kết theo tier ===")
    for tier, stats in by_tier.items():
        print(f"{tier}: {stats['pass']}/{stats['total']} pass")


if __name__ == "__main__":
    main()
