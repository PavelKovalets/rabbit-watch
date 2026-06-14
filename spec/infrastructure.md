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
│   Listens on 0.0.0.0:1234 (OpenAI-compatible /v1, token auth)│
│                                                              │
│   ┌─── Hyper-V Default Switch (NAT, 172.27.144.0/20) ──────┐ │
│   │ Host/gateway: 172.27.144.1                              │ │
│   │                                                         │ │
│   │   ┌── Ubuntu agent VM ──┐                               │ │
│   │   │ 172.27.145.x         │  brain → http://             │ │
│   │   │                      │    172.27.144.1:1234/v1      │ │
│   │   └──────────────────────┘                              │ │
│   └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

Current setup uses the **Hyper-V Default Switch**, not a hand-rolled internal vSwitch.
Confirmed reachable: the host is the guest's default gateway (`172.27.144.1`) and LM
Studio answers on `:1234`. Note the Default Switch picks its 172.x subnet at host boot
and can change across reboots, so the brain resolves the host from the gateway rather
than a hardcoded IP (`ip route | awk '/default/{print $3}'`).

- **GPU access** is HTTP-only: the brain calls LM Studio's OpenAI-compatible API at the
  host gateway (`172.27.144.1:1234`), authenticated with a Bearer token (see
  [decisions.md](decisions.md)). The VM never touches CUDA. Ollama is an acceptable
  swap-in for LM Studio.
- **Egress**: the Default Switch provides NAT, so the guest currently *has* internet
  egress (handy for ntfy.sh in P3). This is looser than the "isolated, no-egress internal
  vSwitch" goal in [decisions.md](decisions.md) — reconcile if stricter isolation is
  wanted (open item below).
- **Webcam**: stays on the host. Capture runs on the host (the producer) and pushes
  frames to host Redis; the guest never sees the USB device. (USB/IP into the guest was
  considered and rejected — see [decisions.md](decisions.md).)

## Assumed host state

For the pipeline to run, the host must provide:

- LM Studio bound to `0.0.0.0:1234` (not just localhost) with a vision-capable Gemma 4
  variant loaded — see [decisions.md](decisions.md) for the model choice — and **API
  token auth enabled**; the token is given to the brain via env/.env (never committed).
- Windows Firewall inbound rules allowing the guest subnet → `host:1234` (model;
  confirmed open) and → `host:6379` (Redis).
- The webcam connected to the host, plus the producer and Redis running on the host.

## Open environment questions

- **Network isolation** — currently the Default Switch (NAT, has egress). If the
  "isolated internal vSwitch, no egress" posture from [decisions.md](decisions.md) is
  required, switch the guest's network and add egress rules only where needed.
- **Camera attach ergonomics** — manual `usbipd attach` per session to start; static
  attach at VM boot is a possible later convenience.
