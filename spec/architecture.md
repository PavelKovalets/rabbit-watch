# Architecture

## Pipeline

Producer–consumer pipeline decoupled by a Redis Stream so the camera captures at full
speed while inference consumes at its own pace:

1. **Producer** (`src/producer/capture.py`) — OpenCV capture loop (default 10 fps),
   JPEG-encodes frames (quality 80) and `XADD`s them to the stream with approximate
   `MAXLEN` trimming (circular buffer in RAM, no disk I/O).
2. **Redis Stream** — the buffer between processes. Stream key and trim length come
   from env vars (see below).
3. **Brain** (`src/brain/inference.py`) — async `XREAD` consumer (blocks 5s, batches
   of 10). Per frame it runs the detection chain: `vision.py` asks Gemma 4 (via
   LM Studio) whether the rabbit is on the couch and for a brief scene description;
   `detector.py` applies the confidence threshold + consecutive-frame smoothing
   (`Confirmer`). Phase 1 de-dups repeats with a cooldown (`Cooldown`); **Phase 2
   replaces that with arrival/departure visit tracking** (open on confirmation, close
   after a sustained absence) so a visit's duration can be measured. The blocking HTTP
   call runs off the event loop via `asyncio.to_thread`. Prompts live in
   `src/brain/prompts.yaml`.
4. **Event log** (`src/brain/events.py`) — one JSON-Lines record per visit at
   `RABBITWATCH_EVENTS_LOG`, with the snapshot JPEG under `RABBITWATCH_OUTPUT_DIR`.
   Phase 1 fields: `{timestamp, confidence, on_couch, snapshot}`. **Phase 2 enriches**
   each record with `start`/`end`/`duration_s` (dwell), a `scene` description, and the
   raw model `response`. A separate **raw-response audit log** (`RABBITWATCH_RESPONSES_LOG`,
   JSON-Lines) records *every* model classification regardless of confirmation (FR-9).
5. **Analytics** (`src/brain/analytics.py`, Phase 2) — reads the event log alone and
   writes a descriptive Excel **`.xlsx`** workbook over the full history (via `openpyxl`):
   a visits sheet (raw data), per-day counts, time-of-day distribution (local timezone),
   and dwell-time stats. Descriptive only — no before/after efficacy claims.
5. **Notifier** (`src/notifier/alert.py`) — `send_ntfy()` posts to ntfy.sh with optional
   image attachment. **Deferred (P3):** present but unused; the MVP is log-only.

Shared infrastructure lives in `src/common/`: `get_redis_client()` returns an async
client (`redis.asyncio`), `get_logger()` for logging.

**Frame contract**: both producer and brain read the same `RABBITWATCH_STREAM` key;
each entry has a `jpeg` field containing raw JPEG bytes. Changes to this format must
land on both sides in the same commit.

## Deployment topology

The pipeline runs inside an **Ubuntu VM on a Windows 11 Pro Hyper-V host**. Hardware,
network addressing, and assumed host state are documented in
[infrastructure.md](infrastructure.md); the points that shape the *software* are:

- **GPU is a network service, not local**: the brain reaches Gemma 4 only via
  LM Studio's OpenAI-compatible API on the host vSwitch IP. Inference code must assume
  HTTP to a remote endpoint, never local CUDA. (Model choice: [decisions.md](decisions.md).)
- **Capture runs on the host**, where the webcam is: the producer and Redis run on the
  host, and the guest brain connects *out* to Redis (`172.27.144.1:6379`). No USB/IP
  into the guest (see [decisions.md](decisions.md)).
- **Isolation is load-bearing**: the guest makes only outbound calls (Redis + model);
  nothing is pushed into it. Don't design anything that requires inbound host→guest
  access or weakens the VM boundary.
- **Redis** lives on the host alongside the producer (`docker-compose` there, or any
  Redis); it is the buffer both sides share.

## Configuration (env vars)

| Variable | Default | Used by |
|---|---|---|
| `RABBITWATCH_REDIS` | `redis://localhost:6379` | common |
| `RABBITWATCH_STREAM` | `rabbit-watch-frames` | producer, brain |
| `RABBITWATCH_MAXLEN` | `1000` | producer |
| `RABBITWATCH_SAVE_FRAMES_TO_DISK` | `False` | producer (debug: also write frames to `data/`) |
| `RABBITWATCH_OUTPUT_DIR` | `data/brain/detections` | brain |
| `RABBITWATCH_VLM_URL` | `http://localhost:1234/v1` | brain (set to host vSwitch IP inside the VM) |
| `RABBITWATCH_VLM_MODEL` | `gemma-4` | brain (name as loaded in LM Studio) |
| `RABBITWATCH_VLM_API_KEY` | _(unset)_ | brain (Bearer token; from env/.env, NFR-6) |
| `RABBITWATCH_VLM_TIMEOUT` | `30` | brain (seconds) |
| `RABBITWATCH_CONF_THRESHOLD` | `0.8` | brain (confidence to count a frame present) |
| `RABBITWATCH_CONSECUTIVE_FRAMES` | `3` | brain (present frames to open a visit) |
| `RABBITWATCH_ABSENCE_FRAMES` | `3` | brain (absent frames to close a visit) |
| `RABBITWATCH_EVENTS_LOG` | `<RABBITWATCH_OUTPUT_DIR>/events.jsonl` | brain (per-visit log) |
| `RABBITWATCH_RESPONSES_LOG` | `<RABBITWATCH_OUTPUT_DIR>/responses.jsonl` | brain (raw-response audit log) |
| `RABBITWATCH_NTFY_TOPIC` | `rabbit-watch` | notifier (deferred, P3) |

Every variable must have a working default (NFR-3 in
[requirements.md](requirements.md)).
