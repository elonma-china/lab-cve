"""Single-lab rerun: verify the fixed _CRITICAL_LINE_RE actually surfaces the
"data" vs "args" warning near the failure feedback on repair iterations."""
import asyncio
import run_pocex as rp

rp.LABS = [
    ("vite-CVE-2026-39363", 5173, "medium", False),
]

if __name__ == "__main__":
    results = asyncio.run(rp.main())
    print("\n\n=== FINAL RESULTS ===")
    for r in results:
        score = r.get("score", 0)
        mark = "✅" if r.get("oracle_pass") else ("⚠️" if score >= 6 else "❌")
        print(f"{mark} {r['id'][:45]:<45} {r.get('tier','?'):<10} {score}/10  "
              f"{r.get('elapsed_s',0):.0f}s  {r.get('evidence','')[:50]}")
