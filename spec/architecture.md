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
   of 10). **Currently a stub:** it only saves frames to `RABBITWATCH_OUTPUT_DIR`. Target
   design: ask Gemma 4 (via LM Studio) whether the rabbit is on the couch, apply
   threshold + temporal smoothing + cooldown, and write confirmed events to the event
   log with a snapshot. Prompt templates live in `src/brain/prompts.yaml`.
4. **Event log + analytics** — confirmed events are appended to a machine-readable log
   (timestamp, confidence, snapshot reference) under `RABBITWATCH_OUTPUT_DIR`; analytics
   are computed from that log alone (incidents/day, time-of-day, trend) to measure
   intervention efficacy. This is the MVP's output, replacing real-time alerting.
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
- **Webcam** arrives in the VM via usbipd-win, so the producer sees an ordinary
  `/dev/video*` device.
- **Isolation is load-bearing**: no external egress by default — features that reach the
  internet (e.g. ntfy.sh in P3) need a per-VM egress rule. Don't design anything that
  requires host access or weakens the VM boundary.
- **Redis** is the only containerized service (`docker-compose up -d`); inference is
  host-side.

## Configuration (env vars)

| Variable | Default | Used by |
|---|---|---|
| `RABBITWATCH_REDIS` | `redis://localhost:6379` | common |
| `RABBITWATCH_STREAM` | `rabbit-watch-frames` | producer, brain |
| `RABBITWATCH_MAXLEN` | `1000` | producer |
| `RABBITWATCH_SAVE_FRAMES_TO_DISK` | `False` | producer (debug: also write frames to `data/`) |
| `RABBITWATCH_OUTPUT_DIR` | `data/brain/detections` | brain |
| `RABBITWATCH_NTFY_TOPIC` | `rabbit-watch` | notifier (deferred, P3) |

Planned for Phase 1 (added as the tasks in [tasks.md](tasks.md) land):

| Variable | Default | Used by |
|---|---|---|
| `RABBITWATCH_VLM_URL` | `http://localhost:1234/v1` | brain (set to host vSwitch IP inside the VM) |
| `RABBITWATCH_VLM_MODEL` | _(model name as loaded in LM Studio)_ | brain |
| `RABBITWATCH_CONF_THRESHOLD` | `0.8` | brain |
| `RABBITWATCH_CONSECUTIVE_FRAMES` | `3` | brain |
| `RABBITWATCH_COOLDOWN_SECONDS` | `300` | brain |
| `RABBITWATCH_EVENTS_LOG` | `<RABBITWATCH_OUTPUT_DIR>/events.jsonl` | brain |

Every variable must have a working default (NFR-3 in
[requirements.md](requirements.md)).
