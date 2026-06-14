# Requirements

What the system must do, stated functionally and kept implementation-free. The *how* —
modules, APIs, models, env vars, file formats — lives in
[architecture.md](architecture.md) and the step-by-step plan in [tasks.md](tasks.md).
Phase tags (P1–P4) map to the roadmap in [objectives.md](objectives.md).

## Functional requirements

- **FR-1** (P1): Continuously observe the monitored scene through the camera.
- **FR-2** (P1): For observed frames, determine whether the rabbit is on the couch,
  together with a confidence score.
- **FR-3** (P1): Confirm a detection only when confidence is high enough and sustained
  across several consecutive observations, so a single ambiguous frame never triggers a
  detection.
- **FR-4** (P1): Treat one couch visit as a single event — after a confirmed event, do
  not raise another until a cooldown has elapsed.
- **FR-5** (P1): Record every confirmed event durably, with its time, confidence, and a
  snapshot of the moment, for later review.
- **FR-6** (P2): Report how often couch visits happen — counts per day, distribution by
  time of day, and trend over time — derived from the recorded events, so the owner can
  compare before and after interventions (spaying, covering the couch).
- **FR-7** (P3, deferred): On a confirmed event, send a real-time notification to the
  owner's phone including the snapshot.
- **FR-8** (P4, deferred, opt-in): Optionally trigger a gentle automated *positive*
  response (e.g. a recall sound paired with a treat). Never an aversive. Off by default.

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
