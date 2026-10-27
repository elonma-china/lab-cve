"""Run a single lab through poc-ex and print JSON result to stdout."""
from __future__ import annotations
import asyncio, json, os, socket, subprocess, sys, time
from pathlib import Path

LAB_ID = sys.argv[1]
PORT = int(sys.argv[2])
TIER = sys.argv[3]
KNOWN_GAP = sys.argv[4].lower() == "true"

sys.path.insert(0, '/home/ict/AIEngines/secai/red-space/poc-ex/src')
os.chdir('/home/ict/AIEngines/secai/red-space/poc-ex')
os.environ.setdefault('POC_EX_VERIFY_ENABLED', 'true')
os.environ.setdefault('POC_EX_ALLOWED_TARGETS', '127.0.0.1/8,172.16.0.0/12,172.17.0.0/16,172.18.0.0/16,10.0.0.0/8')

LAB_DIR = Path('/home/ict/AIEngines/secai/pentest-space2/poc-lab/targets')


def _get_container_ip(lab_id: str, port: int = 80) -> str | None:
    """Return the IP of the container that exposes `port`, not blindly ids[0]."""
    import json as _json
    r = subprocess.run(
        ["docker", "compose", "-f", str(LAB_DIR / lab_id / "docker-compose.yml"), "ps", "-q"],
        capture_output=True, text=True, cwd=str(LAB_DIR / lab_id))
    ids = r.stdout.strip().splitlines()
    if not ids:
        return None
    # Inspect all containers; prefer the one that exposes target port
    fallback_ip = None
    for cid in ids:
        r2 = subprocess.run(["docker", "inspect", cid], capture_output=True, text=True)
        try:
            info = _json.loads(r2.stdout)[0]
        except Exception:
            continue
        exposed = set()
        for k in list((info.get("Config") or {}).get("ExposedPorts") or {}):
            try: exposed.add(int(k.split("/")[0]))
            except (ValueError, IndexError): pass
        for k in list((info.get("HostConfig") or {}).get("PortBindings") or {}):
            try: exposed.add(int(k.split("/")[0]))
            except (ValueError, IndexError): pass
        networks = (info.get("NetworkSettings") or {}).get("Networks") or {}
        # Pick IP from any non-bridge network
        ip = ""
        for net_name, net_info in networks.items():
            candidate = (net_info or {}).get("IPAddress", "")
            if candidate and net_name != "bridge":
                ip = candidate
                break
        if not ip:
            for net_info in networks.values():
                ip = (net_info or {}).get("IPAddress", "")
                if ip:
                    break
        if ip and not fallback_ip:
            fallback_ip = ip
        if port in exposed and ip:
            return ip
    return fallback_ip


def _tcp_open(host, port, timeout=2.0):
    try:
        with socket.create_connection((host, port), timeout=timeout): return True
    except OSError: return False


def _get_lab_network(lab_id: str) -> str | None:
    """Get the docker network name created by this compose project."""
    import json as _json
    r = subprocess.run(
        ["docker", "compose", "-f", str(LAB_DIR / lab_id / "docker-compose.yml"), "ps", "-q"],
        capture_output=True, text=True, cwd=str(LAB_DIR / lab_id))
    ids = r.stdout.strip().splitlines()
    if not ids:
        return None
    # Check all containers to find a non-bridge network
    for cid in ids:
        r2 = subprocess.run(["docker", "inspect", cid], capture_output=True, text=True)
        try:
            info = _json.loads(r2.stdout)[0]
        except Exception:
            continue
        networks = list(((info.get("NetworkSettings") or {}).get("Networks") or {}).keys())
        for n in networks:
            if n != "bridge":
                return n
    return None


def bring_up(lab_id, port, wait_s=120):
    dc = LAB_DIR / lab_id / "docker-compose.yml"
    r = subprocess.run(["docker", "compose", "-f", str(dc), "up", "-d", "--build"],
                       capture_output=True, text=True, timeout=300, cwd=str(LAB_DIR / lab_id))
    if r.returncode != 0:
        print(f"[up-err] {r.stderr[:200]}", file=sys.stderr)
        return False, None
    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        ip = _get_container_ip(lab_id, port)
        if ip and _tcp_open(ip, port):
            network = _get_lab_network(lab_id)
            print(f"[up] {lab_id} ip={ip} network={network}", file=sys.stderr)
            return ip, network
        time.sleep(3)
    return False, None


def tear_down(lab_id):
    dc = LAB_DIR / lab_id / "docker-compose.yml"
    subprocess.run(["docker", "compose", "-f", str(dc), "down", "-v", "--remove-orphans"],
                   capture_output=True, cwd=str(LAB_DIR / lab_id))


def _score(events, stdout_all):
    final = next((e for e in events if e.get("type") == "final"), {})
    if final.get("ok"):
        return 10, final.get("verdict", "oracle pass")[:120]

    low = stdout_all.lower()
    if any(m in low for m in ["root:x:0", "root:*:", "/bin/bash", "flag{", "lab_canary=", "pwned", "secret"]):
        return 8, "sensitive content in stdout"
    if "etc/passwd" in low and "root" in low:
        return 8, "passwd content read"
    if any(m in low for m in ["500", "traceback", "exception", "stack trace", "null pointer",
                               "error executing", "sqlexception", "ognl", "class.forname"]):
        return 4, "target error / abnormal behavior"
    # check if any run steps completed with stdout
    ran = any(e.get("type") == "step" and e.get("name") == "run" and e.get("status") == "ok"
              for e in events)
    if ran:
        if stdout_all.strip():
            return 4, "got HTTP response from target"
        return 2, "connected, script ran"
    recon_ok = any(e.get("name") == "recon" and e.get("status") == "ok" for e in events)
    if recon_ok:
        return 2, "recon ok, endpoint identified"
    return 0, "no connection / crash"


async def run_lab(lab_id, port, description, cve, known_gap):
    from poc_ex.exploit.driver import run_exploit, classify
    from poc_ex.poc.db import PocCatalog
    from poc_ex.sandbox.executor import SandboxExecutor

    catalog = PocCatalog('data/poc_catalog.sqlite3')
    executor = SandboxExecutor()
    case, record, _ = classify(description, cve, catalog)
    target_ip, lab_network = bring_up(lab_id, port)
    if not target_ip:
        return {"id": lab_id, "tier": TIER, "score": 0, "oracle_pass": False,
                "iters": 0, "elapsed_s": 0,
                "evidence": "lab failed to start", "failure_reason": "bring-up failed",
                "known_gap": known_gap}

    network = lab_network or "bridge"
    target = f"{target_ip}:{port}"
    print(f"[run] {lab_id} target={target} network={network}", file=sys.stderr)
    events, stdout_lines = [], []
    t0 = time.monotonic()

    try:
        async for ev in run_exploit(
            catalog=catalog, executor=executor, corpus=None,
            case=case, cve=cve, record=record, message=description,
            target=target, fields={"network": network}, run_id=f"labcve-{lab_id}",
        ):
            events.append(ev)
            if ev.get("type") == "log" and ev.get("stream") == "stdout":
                stdout_lines.append(ev.get("line", ""))
            elif ev.get("type") == "final":
                print(f"[final] ok={ev.get('ok')} v={ev.get('verdict','')[:60]}", file=sys.stderr)
    except Exception as exc:
        print(f"[exc] {exc}", file=sys.stderr)
        events.append({"type": "error", "message": str(exc)})

    elapsed = time.monotonic() - t0
    score, evidence = _score(events, "\n".join(stdout_lines))
    final_ev = next((e for e in events if e.get("type") == "final"), {})
    iters = sum(1 for e in events if e.get("type") == "step" and e.get("name") == "run")
    reason = None
    if score < 10:
        reason = final_ev.get("rca")
        if not reason:
            cats = [t.get("failure_category","") for t in final_ev.get("transcript",[]) if t.get("failure_category")]
            if cats: reason = ", ".join(cats[:5])

    tear_down(lab_id)
    return {"id": lab_id, "tier": TIER, "score": score, "oracle_pass": score==10,
            "iters": iters, "elapsed_s": round(elapsed,1), "evidence": evidence,
            "failure_reason": reason, "known_gap": known_gap}


# Load description from cve_set.jsonl
meta = {}
with open('/home/ict/AIEngines/secai/pentest-space2/poc-lab/cve_set.jsonl') as f:
    for line in f:
        d = json.loads(line)
        if d['id'] == LAB_ID:
            meta = d; break

desc = meta.get("description_for_ai", "")
cve = meta.get("cve")
if cve and "unconfirmed" in str(cve).lower():
    cve = None

result = asyncio.run(run_lab(LAB_ID, PORT, desc, cve, KNOWN_GAP))
print(json.dumps(result))
