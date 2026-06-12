# 🐰 Rabbit-Watch

** Pet project to use local PC with NVIDIA RTX 5090 real-time rabbit detection.**

Rabbit-Watch leverages the massive parallel processing power of the **NVIDIA RTX 5090** and the reasoning capabilities of **Gemma 4** to provide a privacy-first, local-only monitoring solution. By decoupling video ingestion from AI inference via **Redis Streams**, the system achieves low latency and high reliability.
 
## ⚡ Quick Start

Start the services and run the components locally:

- Start Redis (and vLLM if applicable): `docker-compose up -d`
- Configure local environment ([use venv with VS Code](https://code.visualstudio.com/docs/python/python-tutorial), miniconda for Windows is broken and is very hard to configure properly)
- Install dependencies within the venv: `pip install -r requirements.txt`
- Run the producer (camera → Redis): `python -m src.producer.capture`
- Run the brain (Redis → vLLM inference): `python -m src.brain.inference`


---

## 🏗 High-Level Architecture

The system follows a **Producer-Consumer** pattern mediated by an in-memory message bus. This allows the GPU to process frames at its own pace while the camera captures at full speed.

1.  **Producer (The Eyes):** A lightweight Python process that captures raw frames from the USB webcam, performs JPEG compression to save system RAM, and pushes to a Redis Stream.
2.  **Redis Stream (The Buffer):** Resides in your **50GB System RAM**. It acts as a circular buffer (`MAXLEN 100`), ensuring the "Brain" always has access to the most recent frames without disk I/O.
3.  **The Brain (The Logic):** An asynchronous consumer running on the **RTX 5090**. It pulls frames, sends them to a local **vLLM** endpoint, and interprets the scene using Gemma 4.
4.  **The Notifier (The Voice):** A separate module that listens for "Detection" events and triggers mobile alerts via **ntfy.sh** or **Pushover**.

---

## 📂 Project Structure

```text
rabbit-watch/
├── .cursorrules           # AI Agent instructions (RTX 5090 & Redis context)
├── docker-compose.yml     # Orchestrates Redis and vLLM (CUDA 12.8 optimized)
├── requirements.txt       # Dependencies: opencv-python, redis, vllm-client
│
├── src/
│   ├── common/            # Shared logic & Config loaders
│   │   ├── redis_client.py
│   │   └── logger.py
│   │
│   ├── producer/          # INGESTION: Camera -> Redis
│   │   └── capture.py     # OpenCV + JPEG compression loop
│   │
│   ├── brain/             # INFERENCE: Redis -> vLLM (GPU)
│   │   ├── inference.py   # Main logic loop for Gemma 4
│   │   └── prompts.yaml   # Vision LLM prompt templates
│   │
│   └── notifier/          # ACTION: Detection -> Notification
│       └── alert.py       # API integration for mobile pushes
│
└── data/                  # SSD storage for saved detection events