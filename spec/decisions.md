# Decisions

Log of significant technical decisions, newest first. One entry per decision: what was
decided, why, and what was rejected. Add an entry whenever a choice shapes the
architecture, the toolchain, or the workflow — especially when reversing one of these
means real rework.

## 2026-06-18 — Maximize capture by default: threshold 0.0, 1 consecutive frame

**Decision**: Defaults now favour capturing everything: `RABBITWATCH_CONF_THRESHOLD` =
`0.0` (was `0.8`) and `RABBITWATCH_CONSECUTIVE_FRAMES` = `1` (was `3`). Together, any
single frame the model marks `on_couch` — at any confidence — opens a visit. Both stay
configurable to tighten later.

**Why**: A day's real run showed the model detecting rabbits but at low confidence, so
nothing cleared the 0.8 bar — no visits were confirmed and no snapshots saved. While
collecting data to understand the behavior, over-capturing and filtering later beats
missing true positives. Confidence is still recorded per visit (and shown in the
analytics workbook), so noise can be filtered after the fact.

**Trade-off**: at these defaults there is no arrival smoothing (FR-3), so single-frame
false positives become their own (often 0-duration) visits. Accepted for the
data-collection phase; raise `RABBITWATCH_CONSECUTIVE_FRAMES` and/or
`RABBITWATCH_CONF_THRESHOLD` once false positives are the bigger problem.

**Rejected**: keeping `0.8` / `3` (missed real low-confidence, intermittent detections);
removing the knobs entirely (kept configurable so they can be tightened later).

## 2026-06-13 — Phase 2 scope: richer events, dwell tracking, descriptive-only analytics

**Decision**: Phase 2 (1) captures more per visit — a brief **scene description** and the
**raw model response** on each record — plus a **full audit log of every raw model
response** (FR-9); (2) measures **dwell time** by tracking a visit from arrival to
departure, which **replaces the Phase 1 cooldown** (a `VisitTracker` supersedes
`Cooldown`; `RABBITWATCH_ABSENCE_FRAMES` replaces `RABBITWATCH_COOLDOWN_SECONDS`); and
(3) ships **descriptive analytics only** — visits/day, time-of-day (system local tz),
dwell stats — as an Excel **`.xlsx`** workbook generated over the full history.

**Why**: The owner wants to understand the behavior (how often, when, how long) and have
the model's own description of each scene for review. Dwell time needs explicit
visit-end detection, so the cooldown de-dup is subsumed by proper visit boundaries.

**Rejected**: before/after intervention efficacy comparison (dropped — descriptive stats
are enough; proving spay/couch-cover effect is out of scope); terminal/CSV/PNG output
(chose `.xlsx` — one shareable file that opens in Excel); configurable timezone (use the
system local zone).

## 2026-06-12 — Capture + Redis on the host; only the brain runs in the guest

**Decision**: The webcam stays on the host, and the **producer + Redis run on the host**
too. The guest runs only the brain, which connects *out* to the host for both Redis
(`172.27.144.1:6379`) and the model (`172.27.144.1:1234`). Frames flow
host-producer → host-Redis → guest-brain.

**Why**: The pipeline is already decoupled by Redis, so capture needn't live in the
guest. The guest is a cloud-flavoured Ubuntu (`*-azure` kernel) with no `vhci-hcd`
module and no Docker installed — USB/IP passthrough and an in-guest Redis are both extra
setup for no benefit. Running capture where the camera already works is simpler and
keeps the guest's inbound surface at zero (it only makes outbound calls).

**Rejected**: USB/IP webcam passthrough into the guest (needs a `vhci-hcd` kernel module
the azure kernel lacks, host `usbipd-win`, port 3240, and per-session re-attach);
in-guest Redis (Docker isn't installed in the guest).

## 2026-06-12 — Keep LM Studio API auth on; token via env

**Decision**: LM Studio's server requires a Bearer API token, and we keep it that way.
The brain sends `Authorization: Bearer <token>` read from `RABBITWATCH_VLM_API_KEY`
(env or a gitignored `.env`); the token is never committed.

**Why**: The guest currently runs on the Hyper-V Default Switch (NAT, has internet
egress), which is a looser boundary than the originally-planned isolated internal
vSwitch. With egress present, leaving the model endpoint unauthenticated is needless
exposure; an env-supplied token costs almost nothing.

**Rejected**: disabling LM Studio auth (the "plain HTTP on a private network" assumption
in infrastructure.md) — fine only under true network isolation, which is not the current
state. Connection confirmed: host reachable at the Default Switch gateway
`172.27.144.1:1234`.

## 2026-06-12 — Scope pivot: measurement instrument, not automated trainer

**Decision**: Reframe the project from "detect the rabbit on the couch and automatically
deter it" to "detect the rabbit on the couch, log every event, and measure how often it
happens." MVP is **log-only** (no alert, no actuator). Detection is **prompt-level** —
Gemma 4 is asked directly whether the rabbit is on the couch (no ROI geometry). Efficacy
**analytics** (incidents/day, time-of-day, trend) is an explicit goal so the owner can
baseline now and measure whether spaying + covering the couch reduce the behavior.
Real-time alerting and any automated response are deferred (P3/P4).
*(Superseded 2026-06-13: the efficacy / before-after measurement was dropped; analytics
are descriptive only — see the 2026-06-13 entry above.)*

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
