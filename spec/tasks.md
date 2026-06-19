# Tasks

Step-by-step implementation plan, derived from [requirements.md](requirements.md) and
[architecture.md](architecture.md). This is where progress is tracked (the `spec/`
status markers used to live in requirements; they live here now).

Follow the SDD order from [../CLAUDE.md](../CLAUDE.md): **write the tests for a task
before its implementation.** Each task notes the requirement(s) it satisfies. Mark `[x]`
when done.

Status legend for sub-systems: ✅ done · 🟡 partial/stub · ❌ not started.

---

## Phase 1 — Detect & log (MVP)

**Goal**: rabbit-on-couch detection → confirmation (threshold + smoothing + cooldown) →
durable event record with snapshot. Output is the event log; no alerts, no actuators.

Current state: producer ✅; vision client ✅ (`src/brain/vision.py`); prompts.yaml ✅
(couch-specific, structured reply); detection + visit tracking ✅ (`src/brain/detector.py`);
event log ✅ (`src/brain/events.py`); brain loop ✅ (wired, save-every-frame stub
replaced); LM Studio Bearer-token auth ✅ (`RABBITWATCH_VLM_API_KEY`, NFR-6).
real-endpoint smoke test ⏳ (T1.14).

> Note: Phase 2 replaced the Phase 1 `Confirmer`/`Cooldown` (and `test_confirmer.py`/
> `test_cooldown.py`) with `VisitTracker` — the T1.5–T1.8 records below are historical.

Test env: `conda env create -f environment.yml` → run with
`~/miniconda3/envs/rabbit-watch/bin/python -m pytest`.

### 1. Test scaffolding (NFR-5)

- [x] **T1.1** Add `pytest` to `requirements.txt`; create `tests/` with shared fixtures:
  a fake frame stream (yields a scripted sequence of JPEG bytes) and a fake vision
  client (returns scripted verdicts, raises on demand). No real Redis/camera/LM Studio.

### 2. Vision client — "is the rabbit on the couch?" (FR-2 / NFR-2)

- [x] **T1.2** Tests: given a well-formed model response, parse a `Verdict(on_couch:
  bool, confidence: float)`; given malformed JSON, timeout, or connection error, return
  a "not on couch" verdict and log — never raise. (`tests/test_vision.py`)
- [x] **T1.3** Update `src/brain/prompts.yaml`: replace `rabbit_presence` with a
  `rabbit_on_couch` template that asks specifically whether the rabbit is **on the
  couch** and requests a structured `{on_couch, confidence}` reply.
- [x] **T1.4** Implement `src/brain/vision.py`: call the OpenAI-compatible chat
  completions endpoint with the frame image + prompt, parse the structured verdict.
  Config: `RABBITWATCH_VLM_URL` (default `http://localhost:1234/v1`), `RABBITWATCH_VLM_MODEL`.
  Wrap network/parse errors per T1.2.

### 3. Confirmation: threshold + temporal smoothing (FR-3 / NFR-3)

- [x] **T1.5** Tests: a run of N consecutive above-threshold verdicts confirms; a single
  above-threshold frame surrounded by below-threshold does not; below-threshold frames
  never confirm regardless of count. (`tests/test_confirmer.py`)
- [x] **T1.6** Implement a pure (no-I/O) confirmation component holding the recent-verdict
  window (`Confirmer` in `src/brain/detector.py`). Config: `RABBITWATCH_CONF_THRESHOLD`
  (default `0.0`; lowered from `0.8` on 2026-06-18 — see T2.11/decisions),
  `RABBITWATCH_CONSECUTIVE_FRAMES` (default `1`; lowered from `3` on 2026-06-18).

### 4. Event de-duplication: cooldown (FR-4 / NFR-3)

- [x] **T1.7** Tests: after a confirmed event, further confirmations within the cooldown
  produce no new event; once the cooldown elapses, a new confirmation produces a new
  event. Use an injectable clock (no real `sleep`). (`tests/test_cooldown.py`)
- [x] **T1.8** Implement a cooldown gate (`Cooldown` in `src/brain/detector.py`). Config:
  `RABBITWATCH_COOLDOWN_SECONDS` (default `300`).

### 5. Event log + snapshot (FR-5)

- [x] **T1.9** Tests: writing an event appends one machine-readable record (timestamp,
  confidence, snapshot reference) and persists the snapshot; the log is re-readable and
  parseable (round-trip). (`tests/test_events.py`)
- [x] **T1.10** Implement an append-only event log (JSON Lines at
  `RABBITWATCH_EVENTS_LOG`, default `<RABBITWATCH_OUTPUT_DIR>/events.jsonl`) plus snapshot
  write under the output dir (`src/brain/events.py`).

### 6. Wire into the brain loop (FR-1…FR-5 / NFR-2, NFR-4)

- [x] **T1.11** Integration test: feed the fake stream a scripted frame/verdict sequence
  through the full chain (verdict → confirm → cooldown → event log) and assert the exact
  events written — including that an inference failure mid-sequence yields no false
  event and processing continues. (`tests/test_pipeline.py`)
- [x] **T1.12** Replace the save-every-frame stub in `src/brain/inference.py` with the
  chain above (`RabbitCouchDetector`). Preserves the block-and-batch read; the blocking
  vision call runs via `asyncio.to_thread`.
- [x] **T1.13** Add the new `RABBITWATCH_*` vars to the env-var table in
  [architecture.md](architecture.md); flip the sub-system status markers here.
- [ ] **T1.14** Real end-to-end smoke test.
  - *Endpoint half* ✅: verified live — `VisionClient` classifies an image via
    `172.27.144.1:1234` with Bearer auth and returns a parseable verdict (model
    `google/gemma-4-e4b`).
  - *Transport + real-frame inference* ✅: verified live — host producer → host Redis →
    guest brain. Pulled a real 640×480 camera frame off the stream and Gemma 4 returned a
    parseable verdict. (USB/IP rejected — see decisions.md.)
  - *Positive observation* ⏳: with producer + brain both running, confirm an actual
    rabbit-on-couch visit produces exactly one event + snapshot in
    `data/brain/detections/`. This is the only piece left to watch happen for real.

---

## Phase 2 — Richer events + descriptive analytics (FR-2, FR-5, FR-6, FR-9)

Goal: capture more per visit (scene description, raw model response, dwell time), keep a
full raw-response audit log, and produce a descriptive analytics workbook. Analytics are
descriptive only — no before/after efficacy comparison (dropped, see decisions.md).
Output: an Excel `.xlsx` workbook over the full history; time-of-day in the system local
timezone. Same SDD order — tests before implementation.

Status: **all tasks done; 34 tests passing.** Verified live — the model returns scene
descriptions through the new prompt, and `analytics` generates an `.xlsx` over the visit
log.

### A. Scene description, raw response, audit log (FR-2, FR-5, FR-9)

- [x] **T2.1** Tests: `parse_verdict` extracts a `scene` string alongside `on_couch` /
  `confidence`; missing `scene` degrades gracefully (empty string), never raises.
- [x] **T2.2** Update `prompts.yaml` to ask for a brief one-line scene description in the
  JSON reply (`{on_couch, confidence, scene}`).
- [x] **T2.3** Add `scene` to `Verdict` and keep the raw response text; thread both
  through `VisionClient.classify`.
- [x] **T2.4** Tests + impl: append every classification (timestamp, on_couch,
  confidence, scene, raw response) to a raw-response audit log
  (`RABBITWATCH_RESPONSES_LOG`, default `<OUTPUT_DIR>/responses.jsonl`), regardless of
  confirmation (FR-9).
- [x] **T2.5** Extend the per-visit event record (and tests) with `scene` and raw
  `response`.

### B. Visit dwell tracking — replace cooldown (FR-3, FR-4, FR-5)

- [x] **T2.6** Tests: a visit opens when presence is confirmed and closes after
  `RABBITWATCH_ABSENCE_FRAMES` (default 3) consecutive non-detections; the closed visit
  carries `start`, `end`, `duration_s`; a continuous stay yields exactly one record;
  flapping within the absence window does not split it. Injectable clock, no sleeps.
- [x] **T2.7** Implement a `VisitTracker` (replaces `Cooldown`): holds the open visit,
  closes it on sustained absence, emits one enriched record per visit. Retire
  `RABBITWATCH_COOLDOWN_SECONDS`; add `RABBITWATCH_ABSENCE_FRAMES`. Update the env table
  in [architecture.md](architecture.md).
- [x] **T2.8** Rewire `RabbitCouchDetector` / brain loop to the visit model; update the
  integration test for start/end/duration.

### C. Analytics workbook (FR-6)

- [x] **T2.9** Tests over a synthetic event log (fixed records → expected aggregates):
  visits per day, hour-of-day histogram (local tz), dwell-time stats (count, mean,
  median, max). Pure functions over parsed records, no I/O.
- [x] **T2.10** Implement `src/brain/analytics.py`
  (`python -m src.brain.analytics [-o FILE]`): read the event log alone (FR-6
  reproducibility) and write an `.xlsx` workbook via `openpyxl` — sheets for raw visits,
  per-day counts, time-of-day, and a summary (dwell stats). Add `openpyxl` to
  `requirements.txt` / `environment.yml`. No DB, no external services.

### D. Follow-ups

- [x] **T2.11** Lower the capture defaults so low-confidence / intermittent detections
  are still confirmed and their snapshots saved for review: `RABBITWATCH_CONF_THRESHOLD`
  → `0.0` and `RABBITWATCH_CONSECUTIVE_FRAMES` → `1` (both still configurable). Test: at
  the defaults, a single low-confidence `on_couch` verdict opens a visit.
  (2026-06-18, see decisions.md)

---

## Phase 3 — Real-time alerting (FR-7, deferred)

Outline; not in current scope.

- [ ] Add a per-VM egress rule so the VM can reach ntfy.sh.
- [ ] Tests: confirmed event triggers exactly one notification (faked sender); send
  failure is logged and does not block logging or crash the loop.
- [ ] Invoke `send_ntfy()` from the brain on a confirmed event (snapshot attached),
  gated behind an opt-in flag.
