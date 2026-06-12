# Objectives

## Purpose

Rabbit-Watch is a pet project addressing a concrete problem: a pet rabbit jumps onto
the living-room couch and poops there. Rather than an automated "trainer", the system
is a **privacy-first, local-only monitoring instrument** that detects when the rabbit is
on the couch, logs every occurrence, and measures how often it happens — so the owner
can establish a baseline and quantify whether behavioral interventions (spaying,
covering the couch) actually reduce the behavior.

The "detect and automatically deter" idea (water spray / flash / loud sound) was
explicitly dropped on behavioral grounds — see [decisions.md](decisions.md).

## Goals

1. **Detect "rabbit on the couch"** using a local vision LLM (Gemma 4), asked directly
   whether the rabbit is on the couch in each frame — no cloud inference.
2. **Log every confirmed event** with a timestamp, confidence, and snapshot. The MVP is
   **log-only**: no phone alert and no automated response.
3. **Measure intervention efficacy.** Provide analytics over the event log — incidents
   per day, time-of-day distribution, and trend over time — to baseline the current
   rate and show whether spaying and/or covering the couch reduce couch visits.
4. **Stay trustworthy**: minimize false detections (confidence threshold, temporal
   smoothing) so the measured counts are meaningful.
5. **Run unattended**: inference outages, camera hiccups, or malformed model output
   must not require manual intervention.
6. **Preserve privacy and isolation**: frames never leave the machine. The pipeline
   runs in an isolated Ubuntu VM whose sandbox boundary must not be weakened (see
   [architecture.md](architecture.md)).

## Roadmap (phases)

- **Phase 1 (MVP)** — detect rabbit-on-couch → log event (snapshot + metadata).
  Doubles as the pre-intervention baseline.
- **Phase 2** — analytics over the event log (counts, time-of-day, before/after-trend).
- **Phase 3 (deferred, optional)** — real-time phone alert for human-in-the-loop
  redirection. Useful but not required for the measurement goal.
- **Phase 4 (deferred, opt-in only)** — automated *positive* response (e.g. a recall
  sound paired with a treat in the litter box). Never an aversive/punishment.

## Non-goals

- **Automated aversive deterrents** (water, flash, loud sound) — rejected on behavioral
  grounds (rabbits are prey animals; startle causes fear/GI stasis, not learning).
- **Real-time alerting** — deferred to Phase 3; not in the MVP.
- **Detecting pooping specifically** — presence on the couch is the actionable signal;
  posture/defecation detection is out of scope.
- Multi-camera support.
- Detecting anything other than the rabbit on the couch.
- Exhaustive analysis of every captured frame — freshness beats completeness; frames
  may be dropped under load.
- Model training/fine-tuning or GPU-level optimization inside the pipeline (the GPU is
  owned by LM Studio on the host).
