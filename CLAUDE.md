# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Rabbit-Watch: a local-only, privacy-first rabbit detection pipeline. A webcam producer pushes JPEG frames into a Redis Stream; an async consumer ("brain") pulls frames for vision-LLM inference (Gemma 4 served by LM Studio on the Hyper-V host); a notifier sends mobile alerts on detection.

The `spec/` folder is the source of truth:

- [spec/objectives.md](spec/objectives.md) — what the project is for, goals and non-goals, phased roadmap
- [spec/requirements.md](spec/requirements.md) — tech-light functional (FR-*) and non-functional (NFR-*) requirements: the *what*
- [spec/architecture.md](spec/architecture.md) — pipeline, frame contract, env-var table: the *how*
- [spec/infrastructure.md](spec/infrastructure.md) — host/VM environment: hardware, network topology, GPU-as-a-service, webcam access
- [spec/tasks.md](spec/tasks.md) — step-by-step implementation plan and progress tracking, phase by phase
- [spec/decisions.md](spec/decisions.md) — decision log: what was chosen, why, what was rejected

## Development process — Spec Driven Development (mandatory)

For any new feature or behavior change, work in this order:

1. **Update the spec first.** Capture the *what* as functional/non-functional requirements in `spec/requirements.md` (keep it implementation-free); put the *how* and the step-by-step plan in `spec/tasks.md`; amend `spec/objectives.md` / `spec/architecture.md` when goals or structure change. Record any significant choice — new dependency, protocol, model, or reversal of a prior decision — in `spec/decisions.md` with what was rejected and why. If code and spec disagree, the spec wins — fix one or the other explicitly, never silently.
2. **Consolidate the spec.** Before moving on, re-read the `spec/` files as a set and reconcile them. Each fact must live in exactly one canonical home — *what* in requirements.md, *how* in architecture.md, environment in infrastructure.md, plan/progress in tasks.md, *why* in decisions.md, goals/scope in objectives.md. Replace any restatement of a fact owned by another file with a cross-reference to it, and resolve every conflict (between two spec files, or between a spec file and the code). Only proceed once the spec is internally consistent and duplication-free.
3. **Write tests next.** Encode the new/changed requirements as pytest tests before implementing. Tests must run without a webcam, Redis server, or LM Studio available (use fakes/fixtures). Reference requirement IDs (e.g., FR-3) in test names or docstrings.
4. **Implement last.** Write the code until the tests pass, then tick the task off and update the status markers in `spec/tasks.md`.

Do not skip ahead: no implementation without a consolidated spec entry and a failing test that justifies it. Bug fixes follow the same loop with step 1 reduced to confirming the spec already covers the correct behavior.

## Commands

```bash
docker-compose up -d                 # Start Redis (the only containerized service; inference is host-side LM Studio)
pip install -r requirements.txt      # Install deps (use a venv)
python -m src.producer.capture       # Run producer: webcam -> Redis Stream
python -m src.brain.inference        # Run brain: Redis Stream -> consumer
pytest                               # Run tests (no suite exists yet — create tests/ with the first SDD feature)
```

Always run modules with `python -m src.<pkg>.<module>` from the repo root — imports are absolute from `src.`. (`pytest` is not yet in requirements.txt; add it when the first test lands.)

## Key constraints (details in spec/architecture.md)

- The pipeline runs in an isolated Ubuntu VM; the GPU is reached only via LM Studio's OpenAI-compatible HTTP API on the host vSwitch IP — never assume local CUDA, and never weaken the VM sandbox boundary.
- The frame contract (`jpeg` field of raw JPEG bytes on `RABBITWATCH_STREAM`) is shared by producer and brain — change both sides in the same commit.
- All tunables are `RABBITWATCH_*` env vars with working defaults; new ones go into the table in spec/architecture.md.
