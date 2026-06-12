# 🐰 Rabbit-Watch

** Pet project: detect when my pet rabbit is on the living-room couch, log it, and measure how often it happens.**

The rabbit has a habit of jumping on the couch and pooping there. Rabbit-Watch is a privacy-first, local-only **monitoring instrument** that uses **Gemma 4** (on an **NVIDIA RTX 5090**) to spot the rabbit on the couch, log every event with a snapshot, and report how often it happens — so behavioral interventions (spaying, covering the couch) can be measured. By decoupling video ingestion from AI inference via **Redis Streams**, the system stays responsive. See [`spec/objectives.md`](spec/objectives.md) for goals and the deliberate decision *not* to build an automated deterrent.

The pipeline runs inside an **Ubuntu VM on a Windows 11 Hyper-V host**: the webcam is attached into the VM via **usbipd-win**, while the GPU stays on the host and is reached over an internal vSwitch through **LM Studio**'s OpenAI-compatible API (see [`spec/infrastructure.md`](spec/infrastructure.md) for the full topology).
 
## ⚡ Quick Start

Start the services and run the components locally:

- Start Redis: `docker-compose up -d`
- Configure local environment ([use venv with VS Code](https://code.visualstudio.com/docs/python/python-tutorial), miniconda for Windows is broken and is very hard to configure properly)
- Install dependencies within the venv: `pip install -r requirements.txt`
- Run the producer (camera → Redis): `python -m src.producer.capture`
- Run the brain (Redis → LM Studio inference): `python -m src.brain.inference`


---

## 🏗 High-Level Architecture

The system follows a **Producer-Consumer** pattern mediated by an in-memory message bus. This allows the GPU to process frames at its own pace while the camera captures at full speed.

1.  **Producer (The Eyes):** captures webcam frames (attached into the VM via `usbipd attach`), JPEG-compresses them, and pushes to a Redis Stream.
2.  **Redis Stream (The Buffer):** a bounded in-RAM circular buffer — the "Brain" always sees the most recent frames, with no disk I/O.
3.  **The Brain (The Logic):** an async consumer that sends frames across the Hyper-V vSwitch to **LM Studio** on the Windows host (CUDA on the **RTX 5090**), where **Gemma 4** judges whether the rabbit is on the couch. Confirmed events are written to an event log with a snapshot. The VM never touches the GPU directly.
4.  **The Notifier (The Voice):** ntfy.sh mobile alerts — *deferred*; the MVP is log-only (see `spec/`).

Full design docs live in [`spec/`](spec/): [objectives](spec/objectives.md) · [requirements](spec/requirements.md) · [architecture](spec/architecture.md) · [tasks](spec/tasks.md) · [decisions](spec/decisions.md).

---

## 📂 Project Structure

```text
rabbit-watch/
├── CLAUDE.md              # AI agent instructions (SDD workflow & conventions)
├── spec/                  # Source of truth: objectives, requirements, architecture, infrastructure, tasks, decisions
├── docker-compose.yml     # Orchestrates Redis (inference lives on the host, not in Docker)
├── requirements.txt       # Dependencies: opencv-python, redis, requests
│
├── src/
│   ├── common/            # Shared logic & Config loaders
│   │   ├── redis_client.py
│   │   └── logger.py
│   │
│   ├── producer/          # INGESTION: Camera -> Redis
│   │   └── capture.py     # OpenCV + JPEG compression loop
│   │
│   ├── brain/             # INFERENCE: Redis -> LM Studio (host GPU)
│   │   ├── inference.py   # Main logic loop for Gemma 4
│   │   └── prompts.yaml   # Vision LLM prompt templates
│   │
│   └── notifier/          # ACTION: Detection -> Notification
│       └── alert.py       # API integration for mobile pushes
│
└── data/                  # SSD storage for saved detection events