#!/bin/bash
# Run all labs sequentially through poc-ex, collect JSON results
set -euo pipefail

POCEX=".venv/bin/python"
RUNNER="/home/ict/AIEngines/secai/pentest-space2/poc-lab/run_one_lab.py"
RESULTS="/home/ict/AIEngines/secai/pentest-space2/poc-lab/results/pocex_run_results.json"
mkdir -p "$(dirname "$RESULTS")"

cd /home/ict/AIEngines/secai/red-space/poc-ex

export POC_EX_VERIFY_ENABLED=true
export POC_EX_ALLOWED_TARGETS=127.0.0.1/8,172.16.0.0/12,172.17.0.0/16,172.18.0.0/16,10.0.0.0/8
export PYTHONUNBUFFERED=1

RESULTS_ARR="["
FIRST=1

run_lab() {
    local id=$1 port=$2 tier=$3 gap=$4
    echo ""
    echo "============================================================"
    echo "LAB: $id ($tier) port=$port"
    echo "============================================================"

    local out
    if out=$(timeout 400 $POCEX "$RUNNER" "$id" "$port" "$tier" "$gap" 2>/tmp/lab_stderr.txt); then
        echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  score={d['score']} oracle={d['oracle_pass']} iters={d['iters']} {d['elapsed_s']:.0f}s\")"
        if [ "$FIRST" = "1" ]; then
            RESULTS_ARR="${RESULTS_ARR}${out}"
            FIRST=0
        else
            RESULTS_ARR="${RESULTS_ARR},${out}"
        fi
    else
        echo "  [TIMEOUT/ERROR] check /tmp/lab_stderr.txt"
        cat /tmp/lab_stderr.txt | tail -10
        entry="{\"id\":\"$id\",\"tier\":\"$tier\",\"score\":0,\"oracle_pass\":false,\"iters\":0,\"elapsed_s\":400,\"evidence\":\"timeout or runner error\",\"failure_reason\":\"runner timeout\",\"known_gap\":$gap}"
        if [ "$FIRST" = "1" ]; then
            RESULTS_ARR="${RESULTS_ARR}${entry}"
            FIRST=0
        else
            RESULTS_ARR="${RESULTS_ARR},${entry}"
        fi
    fi

    # Save intermediate
    echo "${RESULTS_ARR}]" | python3 -m json.tool > "$RESULTS" 2>/dev/null || true
}

# easy
run_lab "demo-cmdi-001"               8080 "easy"      "false"
run_lab "nextjs-CVE-2025-29927"       3000 "easy"      "false"
run_lab "vite-CVE-2025-30208"         5173 "easy"      "false"
run_lab "langflow-CVE-2026-33017"     7860 "easy"      "false"
# medium
run_lab "gotenberg-CVE-2026-40281"    3000 "medium"    "false"
run_lab "vite-CVE-2026-39363"         5173 "medium"    "false"
run_lab "n8n-CVE-2026-21858"          5678 "medium"    "false"
run_lab "nginx-ui-CVE-2026-27944"     9000 "medium"    "false"
run_lab "rails2shell-CVE-2026-66066"  3000 "medium"    "false"
# excellent
run_lab "wordpress-CVE-2026-63030"      80 "excellent" "false"
run_lab "php2shell-CVE-2026-109618"     80 "excellent" "false"
run_lab "comment2shell-CVE-2026-93485"  80 "excellent" "true"
run_lab "click2shell-CVE-unconfirmed"   80 "excellent" "true"
# inetutils - telnet
run_lab "inetutils-CVE-2026-24061"      23 "easy"      "true"

echo "${RESULTS_ARR}]" | python3 -m json.tool > "$RESULTS"

echo ""
echo "=== SUMMARY ==="
python3 -c "
import json
with open('$RESULTS') as f: results = json.load(f)
total = sum(r['score'] for r in results)
maxs = len(results)*10
passes = sum(1 for r in results if r['oracle_pass'])
print(f'Total: {total}/{maxs}  Oracle passes: {passes}/{len(results)}')
tiers = {}
for r in results:
    t = r['tier']; tiers.setdefault(t,[]).append(r['score'])
for t,s in sorted(tiers.items()):
    print(f'  {t}: avg {sum(s)/len(s):.1f}/10 ({sum(1 for x in s if x==10)}/{len(s)} oracle pass)')
print()
print(f'  {\"ID\":<45} {\"Tier\":<10} {\"Score\":<7} {\"Oracle\":<8} {\"Iters\":<6} {\"Time\":<6}')
print('-'*90)
for r in sorted(results, key=lambda x: (-x[\"score\"], x[\"id\"])):
    mark = \"PASS\" if r[\"oracle_pass\"] else (\"part\" if r[\"score\"]>=6 else \"fail\")
    print(f'  {r[\"id\"]:<45} {r[\"tier\"]:<10} {r[\"score\"]}/10  {mark:<8} {r[\"iters\"]:<6} {r[\"elapsed_s\"]:.0f}s')
    if r[\"failure_reason\"]:
        print(f'    reason: {r[\"failure_reason\"][:80]}')
"
