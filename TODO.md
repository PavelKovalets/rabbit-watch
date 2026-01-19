# rabbit-watch — TODO Plan

- **Webcam Capture:** Implement reliable webcam capture using OpenCV, with frame sampling and drop handling.
- **Preprocessing Pipeline:** Resize, normalize, and batch frames; add optional ROI and low-light enhancement.
- **Vision LLM Integration:** Wire inference to a Vision LLM (local PyTorch/ONNX/TensorRT or cloud API wrapper).
- **Rabbit Detection Logic:** Apply confidence thresholds, temporal smoothing, and optional object localization.
- **Notification System:** Send alerts (Telegram, push, or email) with snapshot when rabbit is detected.
- **RTX 5090 Optimizations:** Use FP16, CUDA/cuDNN/TensorRT or DirectML, and asynchronous I/O for low latency.
- **Logging & False-Positive Handling:** Save detection snapshots, metrics, allow manual review and retraining dataset export.
- **Tests, Demo & Docs:** Add unit tests, a demo runner, and usage docs for quick start.
