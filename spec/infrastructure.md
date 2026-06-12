# Infrastructure

Describes the physical/host environment the pipeline assumes. This is reference, not a
setup runbook: the **why** (compute-proxy vs passthrough, Hyper-V vs WSL2) lives in
[decisions.md](decisions.md), and how the software pipeline maps onto this environment
is in [architecture.md](architecture.md).

The pipeline runs in an isolated Ubuntu VM and reaches the GPU only as a network service.
Isolation is load-bearing — the VM is a sandbox for coding-agent experiments, so nothing
in the design should require host access or weaken the VM boundary.

## Hardware

- **CPU**: AMD Ryzen 9 9950X (Zen 5; integrated RDNA 2 graphics, 2 CUs). The iGPU is the
  host's display fallback if the 5090 ever needs dismounting — not needed by the
  compute-proxy plan.
- **GPU**: NVIDIA RTX 5090 (Blackwell, 32 GB VRAM). Single consumer card — no SR-IOV, no
  vGPU. Stays on the Windows host.
- **OS**: Windows 11 Pro with the Hyper-V role; Ubuntu 22.04 / 24.04 LTS guests (Gen 2).

## Network topology

```
┌─────────────────── Windows 11 Pro Host ─────────────────────┐
│                                                              │
│   LM Studio (Windows-native)  ◄──── RTX 5090 (CUDA)          │
│   Listens on 0.0.0.0:1234 (OpenAI-compatible /v1)            │
│                                                              │
│   ┌─── Hyper-V Internal vSwitch (e.g. 192.168.50.0/24) ────┐ │
│   │ Host: 192.168.50.1                                      │ │
│   │                                                         │ │
│   │   ┌── Ubuntu agent VM ──┐                               │ │
│   │   │ 192.168.50.10        │  brain → http://             │ │
│   │   │                      │    192.168.50.1:1234/v1      │ │
│   │   └──────────────────────┘                              │ │
│   └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

- **GPU access** is HTTP-only: the brain calls LM Studio's OpenAI-compatible API at the
  host's vSwitch IP (`192.168.50.1:1234`). The VM never touches CUDA. Ollama is an
  acceptable swap-in for LM Studio.
- **Egress**: the internal vSwitch has no external egress by default. Anything that must
  reach the internet (e.g. ntfy.sh in a later phase) needs a per-VM egress rule.
- **Webcam**: a host USB webcam is attached into a chosen VM on demand with `usbipd-win`
  (`usbipd attach`); verify in-guest with `v4l2-ctl`.

## Assumed host state

For the pipeline to run, the host must provide:

- LM Studio bound to `0.0.0.0:1234` (not just localhost) with a vision-capable Gemma 4
  variant loaded — see [decisions.md](decisions.md) for the model choice.
- The internal vSwitch up, with a firewall rule allowing guests → `host:1234`.
- The webcam attached to the target VM via `usbipd-win`.

## Open environment questions

- **Webcam vendor/PID** for the `usbipd` bind rule — currently unknown.
- **LM Studio authentication** — plain HTTP on the private vSwitch is fine for solo use;
  revisit if multiple humans or untrusted agents share the host.
- **Camera attach ergonomics** — manual `usbipd attach` per session to start; static
  attach at VM boot is a possible later convenience.
