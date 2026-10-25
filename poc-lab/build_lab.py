#!/usr/bin/env python3
"""Dựng (docker compose up) target(s) theo lô, không chạy PoC/oracle.

Lô được suy từ năm trong mã CVE của từng case trong cve_set.jsonl:
    lô 1 = CVE-2026, lô 2 = CVE-2025. Case không có "cve" (demo) chỉ build khi
    gọi --only.

Chỉ build case đã có targets/<id>/docker-compose.yml ("wired"); case chưa có
sẽ được in ra dưới dạng SKIP (thiếu target), không coi là lỗi build.

Dùng:
    python3 build_lab.py --batch 1          # build toàn bộ case lô 1 đã wired
    python3 build_lab.py --batch 2
    python3 build_lab.py --batch all
    python3 build_lab.py --only langflow-CVE-2026-33017
    python3 build_lab.py --batch 1 --down   # teardown thay vì build
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_cases(path: Path):
    cases = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            cases.append(json.loads(line))
    return cases


def batch_of(case: dict) -> str | None:
    cve = case.get("cve") or ""
    m = re.search(r"CVE-(\d{4})-", cve)
    if not m:
        return None  # demo hoặc case không có CVE thật
    year = m.group(1)
    if year == "2026":
        return "1"
    if year == "2025":
        return "2"
    return None


def is_wired(case_id: str) -> bool:
    return (ROOT / "targets" / case_id / "docker-compose.yml").exists()


def compose(case_id: str, action: str) -> bool:
    compose_file = ROOT / "targets" / case_id / "docker-compose.yml"
    project = f"poclab-{case_id}".lower()
    if action == "up":
        cmd = ["docker", "compose", "-p", project, "-f", str(compose_file), "up", "-d", "--build"]
    else:
        cmd = ["docker", "compose", "-p", project, "-f", str(compose_file), "down", "-v"]
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--batch", choices=["1", "2", "all"], help="lô 1 = CVE-2026, lô 2 = CVE-2025")
    group.add_argument("--only", help="chỉ build 1 case theo id")
    parser.add_argument("--cve-set", default=str(ROOT / "cve_set.jsonl"))
    parser.add_argument("--down", action="store_true", help="teardown thay vì build/up")
    args = parser.parse_args()

    cases = load_cases(Path(args.cve_set))
    if args.only:
        targets = [c for c in cases if c["id"] == args.only]
        if not targets:
            print(f"[!] không thấy id '{args.only}' trong {args.cve_set}", file=sys.stderr)
            sys.exit(1)
    else:
        targets = [c for c in cases if args.batch == "all" or batch_of(c) == args.batch]

    action = "down" if args.down else "up"
    built, skipped, failed = [], [], []

    for case in targets:
        case_id = case["id"]
        if not is_wired(case_id):
            print(f"[skip] {case_id}: chưa có targets/{case_id}/docker-compose.yml")
            skipped.append(case_id)
            continue
        ok = compose(case_id, action)
        (built if ok else failed).append(case_id)

    print("\n=== Tổng kết ===")
    verb = "Teardown" if args.down else "Build"
    print(f"{verb} OK ({len(built)}): {', '.join(built) or '-'}")
    print(f"Thất bại ({len(failed)}): {', '.join(failed) or '-'}")
    print(f"Skip - thiếu target ({len(skipped)}): {', '.join(skipped) or '-'}")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
