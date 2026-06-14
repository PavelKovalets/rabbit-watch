# Objectives

## Purpose

Rabbit-Watch is a pet project addressing a concrete problem: a pet rabbit jumps onto
the living-room couch and poops there. Rather than an automated "trainer", the system
is a **privacy-first, local-only monitoring instrument** that detects when the rabbit is
on the couch and logs every visit — with a snapshot, a brief scene description, and how
long it lasted — then reports how often, when, and for how long it happens.

The "detect and automatically deter" idea (water spray / flash / loud sound) was
explicitly dropped on behavioral grounds — see [decisions.md](decisions.md).

## Goals

1. **Detect "rabbit on the couch"** using a local vision LLM (Gemma 4), asked directly
   whether the rabbit is on the couch in each frame — no cloud inference.
2. **Log every visit** with its start/end time and duration, confidence, a snapshot, a
   brief scene description, and the raw model response — plus a separate audit log of
   every raw model response. The MVP is **log-only**: no phone alert and no automated
   response.
3. **Understand the behavior pattern.** Generate a descriptive analytics workbook (Excel
   `.xlsx`) over the full history — visits per day, time-of-day distribution (local time),
   and dwell-time stats — so the owner can see how often, when, and for how long the
   rabbit is on the couch.
4. **Stay trustworthy**: minimize false detections (confidence threshold, temporal
   smoothing) so the measured counts are meaningful.
5. **Run unattended**: inference outages, camera hiccups, or malformed model output
   must not require manual intervention.
6. **Preserve privacy and isolation**: frames never leave the machine. The pipeline
   runs in an isolated Ubuntu VM whose sandbox boundary must not be weakened (see
   [architecture.md](architecture.md)).

## Roadmap (phases)

- **Phase 1 (MVP)** — detect rabbit-on-couch → log event (snapshot + metadata).
  Establishes the first real data on the behavior.
- **Phase 2** — richer event capture (scene description, raw response, visit dwell time)
  plus descriptive analytics over the event log (visits/day, time-of-day, dwell stats).
- **Phase 3 (deferred, optional)** — real-time phone alert for human-in-the-loop
  redirection. Useful but not required for the measurement goal.
- **Phase 4 (deferred, opt-in only)** — automated *positive* response (e.g. a recall
  sound paired with a treat in the litter box). Never an aversive/punishment.

## Non-goals

- **Automated aversive deterrents** (water, flash, loud sound) — rejected on behavioral
  grounds (rabbits are prey animals; startle causes fear/GI stasis, not learning).
- **Real-time alerting** — deferred to Phase 3; not in the MVP.
- **Before/after intervention efficacy comparison** — analytics are descriptive only
  (how often / when / how long); proving whether spaying or the couch cover "worked" is
  out of scope.
- **Detecting pooping specifically** — presence on the couch is the actionable signal;
  posture/defecation detection is out of scope.
- Multi-camera support.
- Detecting anything other than the rabbit on the couch.
- Exhaustive analysis of every captured frame — freshness beats completeness; frames
  may be dropped under load.
- Model training/fine-tuning or GPU-level optimization inside the pipeline (the GPU is
  owned by LM Studio on the host).
