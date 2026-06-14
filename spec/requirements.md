# Requirements

What the system must do, stated functionally and kept implementation-free. The *how* —
modules, APIs, models, env vars, file formats — lives in
[architecture.md](architecture.md) and the step-by-step plan in [tasks.md](tasks.md).
Phase tags (P1–P4) map to the roadmap in [objectives.md](objectives.md).

## Functional requirements

- **FR-1** (P1): Continuously observe the monitored scene through the camera.
- **FR-2** (P1): For observed frames, determine whether the rabbit is on the couch, with
  a confidence score and a brief description of the scene.
- **FR-3** (P1): Confirm a visit only when confidence is high enough and sustained across
  several consecutive observations, so a single ambiguous frame never starts one.
- **FR-4** (P1/P2): Treat each couch visit as a single record delimited by the rabbit's
  arrival and departure — open a visit when presence is confirmed, close it once the
  rabbit has been absent for a sustained number of observations — so a continuous stay is
  one record, not many. *(Phase 1 used a fixed cooldown; Phase 2 replaces it with
  arrival/departure tracking to measure duration.)*
- **FR-5** (P1/P2): Record every visit durably — its start time, end time and duration,
  confidence, a snapshot, a brief scene description, and the raw model response — for
  later review. *(Phase 1 records time/confidence/snapshot; Phase 2 adds duration, scene
  description, and raw response.)*
- **FR-6** (P2): Generate a descriptive analytics report as an Excel (`.xlsx`) workbook
  over the full visit history — counts per day, distribution by time of day (local time),
  and dwell-time stats, plus the raw visit data — so the owner can see how often, when,
  and for how long the rabbit is on the couch.
- **FR-7** (P3, deferred): On a confirmed event, send a real-time notification to the
  owner's phone including the snapshot.
- **FR-8** (P4, deferred, opt-in): Optionally trigger a gentle automated *positive*
  response (e.g. a recall sound paired with a treat). Never an aversive. Off by default.
- **FR-9** (P2): Log every model classification — the raw response plus the parsed fields
  (on_couch, confidence, scene) and a timestamp — to a separate append-only audit log,
  independent of whether it confirmed a visit, for debugging and review.

## Non-functional requirements

- **NFR-1 — Privacy & locality**: All capture and analysis happen on the owner's
  machine; camera frames and video never leave it. In the current scope (P1–P2) nothing
  is sent off-machine at all.
- **NFR-2 — Unattended resilience**: The system runs unattended for long periods. Camera
  or analysis failures must not crash it, must not produce false events, and must
  recover automatically without manual restarts.
- **NFR-3 — Configurable with zero-config defaults**: Detection tunables (confidence
  threshold, number of consecutive observations, cooldown) and operational settings are
  configurable, but every setting has a working default so the system runs with no
  configuration.
- **NFR-4 — Freshness over completeness**: Detection reflects what is happening now.
  Under load the system favors recent frames and bounds its backlog rather than falling
  behind; dropping older unanalyzed frames is acceptable.
- **NFR-5 — Testable offline**: Behavior is covered by automated tests that run without a
  camera, message buffer, or model endpoint available.
- **NFR-6 — Secrets stay out of the repo**: Credentials (e.g. the inference endpoint API
  token) are supplied via environment / a gitignored `.env` file and are never committed.
