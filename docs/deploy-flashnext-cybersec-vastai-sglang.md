# Runbook: Serve dealignai/Qwen3.8-Flash-Next-CYBERSECURITY-NVFP4 on vast.ai (1× RTX PRO 6000, SGLang)

Verified end-to-end on 2026-10-15. Follow these steps in order — each one fixes a
real failure hit during the first attempt. Skipping a step reproduces that failure.

## 0. What you're deploying

- Model: `dealignai/Qwen3.8-Flash-Next-CYBERSECURITY-NVFP4` (HF, not gated).
  ModelOpt NVFP4 quant of Qwen3.8-Flash-Next, `qwen4_exp` architecture,
  uncensored/abliterated, cybersecurity domain-tuned. 422 files, ~126 GB on disk.
  Includes a ~51 GB FP8 PLE (n-gram) table — this is the thing that will OOM you
  if you skip step 2.
- Target: **1× NVIDIA RTX PRO 6000 Blackwell (96 GB VRAM), TP=1**, via SGLang (pip).
- Do NOT use vLLM for this checkpoint on this hardware — vLLM's `qwen4_exp` +
  ModelOpt-NVFP4 mixed-precision loader requires a nightly/branch build, not
  guaranteed in stable `pip install vllm`. SGLang 0.5.21 (stable pip) already
  has native support (`ModelOptModelLoader`, `Qwen4ExpForConditionalGeneration`).

## 1. Choosing the vast.ai offer — do this BEFORE renting

Search:
```bash
vastai search offers --url https://cloud.vast.ai \
  'gpu_name="RTX_PRO_6000_WS" num_gpus=1 cpu_ram>=230 disk_space>=300 reliability>0.95' \
  -o 'dph_total' --raw
```

Hard requirements, not suggestions:
- **`cpu_ram >= 230` in the search listing.** The model needs host RAM for the
  pinned PLE table (~51 GB) plus large transient buffers during weight load and
  FlashInfer kernel autotune. A host listed at ~125 GB RAM gave an actual
  **container cgroup cap of only 183 GB**, and the process got OOM-killed
  (`exit code: -9`) during CUDA-graph/autotune — peak RAM usage was observed
  climbing to 182 GB before the crash. A host listed at ~251 GB RAM gave a
  cgroup cap of ~259 GB, which worked (peak observed ~210 GB, steady-state ~123 GB
  after warmup). **The listed `cpu_ram` is not the real cgroup limit — verify
  on the box with `cat /sys/fs/cgroup/memory.max` after boot, before loading
  anything.**
- **`reliability2 > 0.98`.** A host at 0.962 reliability got stuck for 10+
  minutes on a plain Docker image pull ("Verifying Checksum") and never
  progressed — wasted rental time. Don't rent below ~0.98 for this workload.
- Disk ≥ 300 GB (model is ~126 GB; leave room for caches).

## 2. Image choice — do NOT use the Penny Royal / sglang-rtxpro6000 image directly

`ghcr.io/jpezzulli/sglang-rtxpro6000` is built on **Fedora 44** and does not
install `openssh-server`. vast.ai's automatic SSH-key injection (used by both
`--ssh --direct` launch mode AND args/entrypoint launch mode — it's baked into
every vast.ai instance boot) tries to write to `/etc/ssh/sshd_config` and
`/etc/banner`. On this image `/etc/ssh/` doesn't exist, so that step fails with:

```
... did not complete successfully: exit code: 2
```

and the instance flips to `cur_state: stopped` — you never get SSH access, no
matter which `vastai create instance` launch mode you use. This is not fixable
by changing CLI flags; it requires rebuilding the image with openssh-server, which
is not worth it. **Use a plain Ubuntu/CUDA devel image instead:**

```
nvidia/cuda:13.0.1-devel-ubuntu24.04
```

and install SGLang yourself via pip (next step). This also sidesteps needing
Docker-in-Docker.

## 3. Create the instance

```bash
VASTAI=/home/ict/.local/bin/vastai
HF_TOKEN=$(cat ~/.cache/huggingface/token)   # not required (model isn't gated) but harmless to set

$VASTAI create instance <OFFER_ID> --url https://cloud.vast.ai \
  --image nvidia/cuda:13.0.1-devel-ubuntu24.04 \
  --disk 300 \
  --ssh --direct \
  --env "-p 8000:8000 -e HF_TOKEN=$HF_TOKEN" \
  --onstart-cmd "apt-get update -qq && apt-get install -y -qq python3-pip python3-venv git curl ninja-build build-essential > /tmp/apt.log 2>&1; python3 -m venv /opt/venv; /opt/venv/bin/pip install -q --upgrade pip; /opt/venv/bin/pip install -q 'sglang[all]' hf_transfer > /tmp/pip.log 2>&1; echo DONE_SETUP > /tmp/setup_complete" \
  --label <your-label>
```

Critical details baked into that command, each one a lesson from a real failure:

- **`--ssh --direct`, never `--entrypoint`/`--args`.** The `--entrypoint`/`--args`
  "args launch mode" explicitly opts OUT of vast.ai's SSH injection (per
  `vastai create instance --help`: *"If you use args/entrypoint launch mode,
  we create a container from your image as is, without attempting to inject
  ssh"*). Always use `--ssh --direct` + `--onstart-cmd` for anything you need
  to debug interactively.
- **Install `ninja-build` and `build-essential` in the SAME onstart command**,
  not after. SGLang JIT-compiles custom CUDA kernels (e.g.
  `grouped_gemma_rmsnorm`) on first load. Without `ninja` on PATH it fails with
  `FileNotFoundError: [Errno 2] No such file or directory: 'ninja'` — AFTER
  weights have already loaded into VRAM, wasting that time.
- Check offer ID validity: **each offer ID is single-use.** If you reuse one
  (e.g. retry after a failed create), the API returns `{"success": false}`
  silently while still provisioning something — destroy it and search fresh
  offers rather than retrying the same ID.

## 4. Wait for boot, verify before proceeding

```bash
# Poll until actual_status flips to running AND SSH responds:
vastai show instance <ID> --url https://cloud.vast.ai --raw | python3 -c "
import json,sys
d=json.loads(sys.stdin.read(), strict=False)   # strict=False: status_msg can contain raw control chars
print(d.get('actual_status'), d.get('cur_state'), d.get('ssh_host'), d.get('ssh_port'))
"
```

Once SSH responds, immediately verify — don't assume:

```bash
ssh -p <PORT> root@<HOST> "
  nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
  cat /sys/fs/cgroup/memory.max   # CONFIRM this is >= ~230000000000 bytes before continuing
"
```

If the cgroup max is below ~220 GB, destroy and re-rent on a bigger-RAM offer
now — don't find out after a 10-minute model download + load.

## 5. Download the model

Not gated — no HF login needed, but set `HF_TOKEN` anyway (harmless, avoids
unauthenticated rate limits).

```bash
mkdir -p /root/models
setsid nohup /opt/venv/bin/python3 -c "
from huggingface_hub import snapshot_download
path = snapshot_download(
    repo_id='dealignai/Qwen3.8-Flash-Next-CYBERSECURITY-NVFP4',
    local_dir='/root/models/dealignai-flashnext-cybersec',
    max_workers=8,
)
print('DOWNLOAD_DONE', path)
" > /root/download.log 2>&1 < /dev/null &
```

Took ~10-25 min depending on host bandwidth (observed 422 files, ~126 GB final
size on disk via `du -sh`). Watch for `DOWNLOAD_DONE` in the log; the tqdm
progress bar can stall-looking near the end (large PLE shards, ~5 GB each) —
that's normal, not a hang, as long as the process is still alive
(`ps aux | grep python`).

## 6. Launch the server — exact flags

```bash
cd /root
setsid nohup /opt/venv/bin/python3 -m sglang.launch_server \
  --model-path /root/models/dealignai-flashnext-cybersec \
  --host 0.0.0.0 --port 8000 \
  --tp 1 \
  --trust-remote-code \
  --quantization modelopt_fp4 \
  --attention-backend flashinfer \
  --kv-cache-dtype fp8_e4m3 \
  --mem-fraction-static 0.85 \
  --ple-offload-backend pinned \
  > /root/server.log 2>&1 < /dev/null &
```

Flag notes:
- **`--ple-offload-backend pinned`, never `file`.** SGLang has a `file`-backed
  PLE option (memory-maps the table from disk instead of pinning it in RAM),
  but it is **hard-blocked on discrete-VRAM GPUs**:
  ```
  ValueError: --ple-offload-backend file needs a device whose pageable host
  memory accesses go through the host page tables (unified-memory parts such
  as GB10). This device reports it does not; use --ple-offload-backend pinned.
  ```
  It only works on NVIDIA DGX Spark (GB10, unified memory). On RTX PRO 6000
  (discrete VRAM + separate host RAM over PCIe), `pinned` is the only valid
  choice — which is why step 1's RAM requirement matters so much.
- `--quantization modelopt_fp4` + `--kv-cache-dtype fp8_e4m3` +
  `--attention-backend flashinfer` match this checkpoint's card exactly.
- Expect ~80.7 GB VRAM used after weight load (NVFP4 experts + BF16 dense
  layers), ~13 GB VRAM free for KV cache/CUDA graphs. That's tight but fine for
  single-request testing (max_running_requests capped to 5 by the mamba state
  cache at these settings).
- **Add `--reasoning-parser qwen3 --tool-call-parser qwen3_coder` if you plan
  to test this model as a coding agent (OpenCode, Claude-Code-style clients,
  etc.).** Without them, the model still *generates* correct-looking
  `<think>...</think>` and `<tool_call><function=...>` XML blocks (it knows
  the format), but the OpenAI-compatible API just dumps that raw text into
  `content` — the client never sees a real `tool_calls` field, so agentic
  clients can't execute anything; you'll see the literal XML printed instead
  of a tool being called. Verified with OpenCode: before adding the parsers,
  `Read`/`Edit` tool calls leaked as raw text; after restarting with both
  flags, `Read` and `Edit` executed for real (confirmed via file diff).
  Second load after the first one (same `--model-path`, weights already on
  local disk) completes in ~90s instead of ~165s — restarting to add flags you
  forgot is cheap, not a reason to over-plan the first launch command.

## 7. SSH footguns to avoid while iterating on steps 5-6

- **`pkill -f <pattern>` self-matches.** If you run
  `ssh ... "pkill -9 -f launch_server; ..."`, the remote shell's own command
  line contains the string `launch_server` (because you just typed it into the
  SSH command), so `pkill -f` kills the SSH session's own shell before it can
  do anything else — the whole SSH call exits 255 with zero output. Fix: use
  the bracket trick so the pattern doesn't match itself:
  `pkill -9 -f '[l]aunch_server'`.
- **Long-running remote commands need `setsid` + redirected stdin + `disown`**
  (`setsid nohup ... < /dev/null &`), or an SSH network hiccup kills the whole
  process tree with it. Plain `nohup cmd &` without `setsid`/`< /dev/null` was
  observed to die silently on a transient SSH disconnect.
- When parsing `vastai show instance --raw` output with `json.load`, pass
  `strict=False` — `status_msg` can contain literal control characters
  (newlines from shell script text) that break strict JSON parsing with
  `Invalid control character at: ...`.

## 8. Health check sequence

```bash
curl -s -o /dev/null -w 'HTTP %{http_code}\n' http://localhost:8000/health
curl -s http://localhost:8000/get_model_info     # confirm model_type == "qwen4_exp"
curl -s http://localhost:8000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "/root/models/dealignai-flashnext-cybersec",
    "messages": [{"role":"user","content":"Explain in 2 sentences what CWE-89 is."}],
    "max_tokens": 300,
    "temperature": 0.3,
    "chat_template_kwargs": {"enable_thinking": false}
  }'
```

Check `finish_reason: "stop"` (not `"length"`, which means your `max_tokens`
cut it off mid-answer — bump it, especially if `enable_thinking` is left at
its default `true`, since the `<think>...</think>` block consumes tokens too
and will leak into `content` unless you set a `reasoning_parser` or disable
thinking per-request as shown above).

## 9. External access — find the REAL port

vast.ai remaps your container's internal port to a different external port.
Don't assume `:8000` is reachable from outside — check:

```bash
vastai show instance <ID> --url https://cloud.vast.ai --raw | python3 -c "
import json,sys
d=json.loads(sys.stdin.read(), strict=False)
print('public_ip:', d.get('public_ipaddr'))
print('port map:', d.get('ports'))   # e.g. {'8000/tcp': [{'HostPort': '11332'}]}
"
```

The externally reachable endpoint is `http://<public_ipaddr>:<mapped_host_port>/v1`,
not `:8000`.

## 10. Security note

The server starts with **no API key** by default — anyone with the IP:port can
use it (burns your rented VRAM/compute). For anything beyond a quick personal
test, add `--api-key <token>` to the launch command in step 6, and pass that
key as a Bearer token from the client. Destroy the instance
(`vastai destroy instance <ID>`) the moment you're done — billing is per-hour
from creation, not from first use.

## Summary of root causes (quick-reference table)

| Symptom | Root cause | Fix |
|---|---|---|
| SSH setup exits `code: 2`, instance flips to `stopped` | Image (Fedora-based) lacks `openssh-server` | Use a plain Ubuntu/CUDA image instead |
| `FileNotFoundError: ninja` after weights already loaded | `ninja-build` not installed | Install it in the same onstart command, before first launch |
| SSH command returns exit 255, no output | `pkill -f` matched its own invocation | Use `pkill -f '[p]attern'` bracket trick |
| `RuntimeError: ... scheduler died ... exit code -9` | Host RAM cgroup cap too low for the 51 GB pinned PLE table + transient load/autotune buffers | Rent a host with cgroup RAM ≥ ~230 GB (verify via `/sys/fs/cgroup/memory.max`, not the search listing) |
| `ValueError: --ple-offload-backend file needs a device whose pageable host memory...` | `file` PLE backend only works on unified-memory GPUs (DGX Spark), not discrete VRAM cards | Use `--ple-offload-backend pinned` |
| Model output cut off mid-sentence | `max_tokens` too low relative to reasoning + answer length | Raise `max_tokens`, or set `chat_template_kwargs: {"enable_thinking": false}` |
| curl to `:8000` from outside times out | vast.ai remaps container ports | Check `ports` field in `vastai show instance --raw`, use the mapped host port |
| Agentic client (OpenCode etc.) shows raw `<tool_call>` XML in chat instead of executing a tool | Server missing `--tool-call-parser qwen3_coder` (and `--reasoning-parser qwen3` for `<think>` leakage) | Restart server with both flags; cheap since weights are already on local disk |

## 11. Testing as a coding agent (OpenCode)

Add a custom provider in `~/.config/opencode/opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "dealignai-flashnext": {
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://<public_ip>:<mapped_port>/v1",
        "apiKey": "none"
      },
      "models": {
        "flashnext-cybersec": {
          "name": "dealignai-flashnext-cybersec",
          "id": "/root/models/dealignai-flashnext-cybersec"
        }
      }
    }
  }
}
```

Then: `opencode models dealignai-flashnext` (sanity check it's registered), and
`opencode run --model dealignai-flashnext/flashnext-cybersec "<prompt>"`.

Create test files **inside the directory you run `opencode` from** — OpenCode's
permission system auto-rejects tool calls targeting paths outside the current
project root (`external_directory` permission), which looks like a model
failure but isn't.

## 12. Known quirk: intermittent Chinese-language leakage in non-Chinese output

Observed once in a long multi-turn Vietnamese conversation (after a truncated
response + user sent "continue"): the model's reasoning trace and final
structured-list output started using literal Chinese scaffolding
(`第1行:`, `第2行:`, i.e. "line N" labels) even though nothing in the
conversation was in Chinese. Could not reliably reproduce it on demand (tried
~4 variations: plain Vietnamese list request, simulated truncated+"continue"
turn, higher temperature — all came back clean or empty).

This is **not specific to this checkpoint or to SGLang** — it's a widely
reported, unresolved training-alignment artifact across CJK-origin reasoning
LLMs: see `zai-org/GLM-5#54` (GLM switches to Chinese mid-conversation, worse
in long sessions, model can't detect it happened when asked), `MiniMax-AI/
MiniMax-M2#100` (same across Korean/Spanish/Portuguese/English/Russian/German,
acknowledged as a known badcase), `deepseek-ai/DeepSeek-V3#1642`/`#1226`
(same, closed unfixed). One grounded root-cause example from
`MemTensor/MemOS#2469`: a literal Chinese example phrase anywhere in a
system/tool prompt can prime the model to echo Chinese under long reasoning —
worth auditing OpenCode's own system prompt / tool schemas for this.

Separately, `sgl-project/sglang#36537` documents a **real bug specific to this
model family on SGLang**: Qwen3.8-Flash-Next + `qwen3_coder` tool parser can
loop/desync when speculative decoding (NEXTN/MTP) is combined with reasoning
under long/concurrent sessions (fixed via PRs #36556/#36845). Not confirmed to
be the same root cause as the language leak, but worth knowing if you ever
enable `--speculative-algorithm NEXTN` on this model — this deployment does
not enable it, so it's lower risk here.

No confirmed fix exists for the core language-flip itself. Mitigations with
some support in the issues above, roughly in priority order:
1. Don't use "continue" after a truncated response — reissue the full pending
   request in a fresh message instead of relying on history continuation.
2. Audit every prompt layer in your client (system prompt, tool schemas,
   few-shot examples) for literal non-target-language text that could prime
   the model.
3. If you ever enable speculative decoding for this model, watch for the
   sglang#36537 failure mode specifically.
