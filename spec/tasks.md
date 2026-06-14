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
(couch-specific, structured reply); confirmation + cooldown ✅ (`src/brain/detector.py`);
event log ✅ (`src/brain/events.py`); brain loop ✅ (wired, save-every-frame stub
replaced); LM Studio Bearer-token auth ✅ (`RABBITWATCH_VLM_API_KEY`, NFR-6). Automated
tests ✅ (26 passing); real-endpoint smoke test ⏳ (T1.14).

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
  (default `0.8`), `RABBITWATCH_CONSECUTIVE_FRAMES` (default `3`).

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

## Phase 2 — Analytics / efficacy measurement (FR-6)

Outline; expand into tasks when Phase 1 lands.

- [ ] Define the report: incidents per day, time-of-day histogram, rolling trend.
- [ ] Tests over a synthetic event log (fixed records → expected aggregates).
- [ ] Implement a reporter that reads only the persisted event log (no in-memory state)
  and emits the metrics (CLI/printed summary to start).
- [ ] Capture a pre-intervention baseline; re-run after spaying and after the couch
  cover to compare.

---

## Phase 3 — Real-time alerting (FR-7, deferred)

Outline; not in current scope.

- [ ] Add a per-VM egress rule so the VM can reach ntfy.sh.
- [ ] Tests: confirmed event triggers exactly one notification (faked sender); send
  failure is logged and does not block logging or crash the loop.
- [ ] Invoke `send_ntfy()` from the brain on a confirmed event (snapshot attached),
  gated behind an opt-in flag.
