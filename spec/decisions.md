# Decisions

Log of significant technical decisions, newest first. One entry per decision: what was
decided, why, and what was rejected. Add an entry whenever a choice shapes the
architecture, the toolchain, or the workflow — especially when reversing one of these
means real rework.

## 2026-06-12 — Scope pivot: measurement instrument, not automated trainer

**Decision**: Reframe the project from "detect the rabbit on the couch and automatically
deter it" to "detect the rabbit on the couch, log every event, and measure how often it
happens." MVP is **log-only** (no alert, no actuator). Detection is **prompt-level** —
Gemma 4 is asked directly whether the rabbit is on the couch (no ROI geometry). Efficacy
**analytics** (incidents/day, time-of-day, trend) is an explicit goal so the owner can
baseline now and measure whether spaying + covering the couch reduce the behavior.
Real-time alerting and any automated response are deferred (P3/P4).

**Why**: Rabbits are prey animals — startle-based aversives (water/flash/sound) cause
fear and GI-stasis risk, not learning, and can damage the human bond. The behaviorally
sound role for automation is a human-in-the-loop monitor and a measurement tool for the
owner's real interventions (spay, couch cover). Logging first also captures a
pre-intervention baseline.

**Rejected**: automated aversive deterrent (original idea); detecting "pooping"
specifically (presence on the couch is the actionable signal and far more tractable);
ROI/zone detection for v1 (prompt-level is simpler and leans on the model's scene
understanding).

## 2026-06-12 — Spec Driven Development, homegrown

**Decision**: Mandatory spec → tests → implement order for all feature work, with
`spec/` (objectives, requirements, architecture, decisions) as the source of truth.
Workflow is enforced via CLAUDE.md, not tooling.

**Why**: Keeps design intent and implementation status explicit without process
overhead.

**Rejected**: GitHub Spec Kit — tried it (constitution, generated spec, slash-command
workflow) and reverted: too much ceremony for a small pet project.

## 2026-06-12 — Inference via LM Studio compute proxy (not vLLM, not passthrough)

**Decision**: The RTX 5090 stays on the Windows host running LM Studio
(OpenAI-compatible `/v1` API, port 1234). The brain calls it over HTTP across an
internal Hyper-V vSwitch. The commented-out vLLM service was removed from
docker-compose.yml.

**Why**: Agents/pipelines only need to *call* models, not run CUDA. LM Studio covers
LLM + vision natively on Windows and is already configured. Ollama is the acceptable
swap-in.

**Rejected**: vLLM/SGLang on host (Linux-native, would need WSL2 or a passthrough VM);
DDA full GPU passthrough (unsupported on Win11 Pro, fragile); GPU-P partitioning
(immature Linux-guest support). Environment details in
[infrastructure.md](infrastructure.md).

## 2026-06-12 — Pipeline runs inside an isolated Ubuntu VM on Hyper-V

**Decision**: Producer, Redis, and brain run in an Ubuntu VM (Gen 2) on a Windows 11
Pro Hyper-V host. The webcam attaches via usbipd-win on demand. No external egress by
default; isolation is the load-bearing constraint.

**Why**: Kernel separation and snapshot/checkpoint workflows for sandboxed
coding-agent experiments.

**Rejected**: WSL2 — shared kernel, auto-mounted `/mnt/c`, default Windows interop;
wrong shape for isolation sandboxes.

## 2026-06-11 — Gemma 4 as the vision model (replacing Qwen3-VL)

**Decision**: Gemma 4 (vision-capable variant, sized to the 5090's 32 GB VRAM) is the
inference model, loaded in LM Studio.

**Why**: Most capable open multimodal family at decision time, with native
vision support and official serving support across local stacks.

**Rejected/superseded**: Qwen3-VL (original project plan); Llama 3.2 Vision and
Qwen 2.5 VL (earlier candidates before this decision).

## (original scaffolding) — Redis Streams as the frame buffer

**Decision**: Producer and brain are decoupled by a Redis Stream used as a bounded
in-RAM circular buffer (approximate `MAXLEN` trimming); freshness over completeness —
frames are dropped under load rather than queued.

**Why**: The camera captures at full speed while inference consumes at its own pace;
no disk I/O in the hot path; the brain always sees recent frames.

## (original scaffolding) — ntfy.sh for mobile alerts

**Decision**: Detection alerts go to the owner's phone via ntfy.sh topic push with a
snapshot attachment.

**Why**: Zero-infrastructure push notifications; one HTTP POST, no app backend.
Note: requires a per-VM egress rule (VM has no external egress by default).
