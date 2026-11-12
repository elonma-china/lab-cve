"""Fast iteration runner: only the 5 previously-unsolved labs most relevant to
this round's fixes (probe recv-before-send, probe schema shape, dependency-graph
hint, probe-before-commit generally) — skips the 4 easy already-passing labs and
the 2 browser-dependent labs (comment2shell/click2shell) whose CWE-79 gate isn't
wired through the API yet, so a run there would just fail on that known gap."""
import asyncio
import run_pocex as rp

rp.LABS = [
    ("langflow-CVE-2026-33017",     7860, "easy",      False),
    ("inetutils-CVE-2026-24061",      23, "easy",      True),
    ("vite-CVE-2026-39363",         5173, "medium",    False),
    ("n8n-CVE-2026-21858",          5678, "medium",    False),
    ("wordpress-CVE-2026-63030",      80, "excellent",  False),
]

if __name__ == "__main__":
    results = asyncio.run(rp.main())
    print("\n\n=== FINAL RESULTS ===")
    total, passes = 0, 0
    for r in results:
        score = r.get("score", 0)
        total += score
        if r.get("oracle_pass"):
            passes += 1
        mark = "✅" if r.get("oracle_pass") else ("⚠️" if score >= 6 else "❌")
        print(f"{mark} {r['id'][:45]:<45} {r.get('tier','?'):<10} {score}/10  "
              f"{r.get('elapsed_s',0):.0f}s  {r.get('evidence','')[:50]}")
    print(f"\nTotal: {total}/50  Oracle passes: {passes}/5")
