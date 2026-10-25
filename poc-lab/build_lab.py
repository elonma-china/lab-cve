#!/usr/bin/env python3
"""Dựng (docker compose up) target(s) theo lô, không chạy PoC/oracle.

Lô được suy từ năm trong mã CVE của từng case trong cve_set.jsonl:
    lô 1 = CVE-2026, lô 2 = CVE-2025. Case không có "cve" (demo) chỉ build khi
    gọi --only.

Chỉ build case đã có targets/<id>/docker-compose.yml ("wired"); case chưa có
sẽ được in ra dưới dạng SKIP (thiếu target), không coi là lỗi build.

Dùng:
    python3 build_lab.py --batch 1 --list          # xem STT + tên lab trong lô 1, chưa build gì
    python3 build_lab.py --batch 1                 # build toàn bộ case lô 1 đã wired
    python3 build_lab.py --batch 1 --select 1,3,5  # chỉ build case số 1, 3, 5 trong lô 1
    python3 build_lab.py --batch 1 --select 1-3    # 3 case đầu lô 1
    python3 build_lab.py --batch 1 --select all    # tương đương không truyền --select
    python3 build_lab.py --batch 2
    python3 build_lab.py --batch all
    python3 build_lab.py --only langflow-CVE-2026-33017
    python3 build_lab.py --batch 1 --down          # teardown thay vì build
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


def print_table(cases: list[dict]):
    print(f"{'STT':<4} {'Lab (id)':<40} {'CVE':<20} {'Tier':<10} {'Trạng thái'}")
    for i, case in enumerate(cases, start=1):
        status = "wired" if is_wired(case["id"]) else "thiếu target"
        print(f"{i:<4} {case['id']:<40} {case.get('cve') or '-':<20} {case.get('tier', '-'):<10} {status}")


def parse_select(expr: str, n: int) -> list[int]:
    """'1,3,5-8' hoặc 'all' -> list chỉ số 1-based đã lọc trùng, trong khoảng [1, n]."""
    if expr.strip().lower() == "all":
        return list(range(1, n + 1))
    picked: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            picked.update(range(int(a), int(b) + 1))
        else:
            picked.add(int(part))
    out = sorted(x for x in picked if 1 <= x <= n)
    missing = sorted(picked - set(out))
    if missing:
        print(f"[!] bỏ qua STT ngoài danh sách: {missing}", file=sys.stderr)
    return out


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
    parser.add_argument("--list", action="store_true", help="chỉ in STT + tên lab theo lô, không build")
    parser.add_argument(
        "--select",
        help="lọc theo STT trong --list của lô đã chọn, ví dụ '1,3,5-8' hoặc 'all' (mặc định)",
    )
    args = parser.parse_args()

    cases = load_cases(Path(args.cve_set))
    if args.only:
        targets = [c for c in cases if c["id"] == args.only]
        if not targets:
            print(f"[!] không thấy id '{args.only}' trong {args.cve_set}", file=sys.stderr)
            sys.exit(1)
    else:
        targets = [c for c in cases if args.batch == "all" or batch_of(c) == args.batch]

    if args.list:
        print_table(targets)
        return

    if args.select and not args.only:
        idx = parse_select(args.select, len(targets))
        targets = [targets[i - 1] for i in idx]

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
