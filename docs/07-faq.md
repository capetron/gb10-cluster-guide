# 07. Frequently asked questions

**Summary.** Short answers, each pointing at the document with the evidence. If a
question is not here, open an issue with your command line and output.

## Cables and ports

**What cable do I need to connect two GB10 workstations?**
One 0.5 m QSFP112 passive DAC to the NVIDIA-approved spec (Amphenol NJAAKK0006 /
Luxshare LMTQF022-SD-R), QSFP Port 0 to QSFP Port 0. That is the whole two-node build on
the cable side. [01-hardware.md](01-hardware.md), [02-two-and-three-nodes.md](02-two-and-three-nodes.md).
Cable: https://petronellatech.com/hardware/dgx-spark-cluster-cable/

**The cable says 400G. Do I get 400G?**
No. The GB10's ConnectX-7 port is documented at up to 200 Gb/s and the cable negotiates
at 200G. The 400G rating is the cable's capability and buys headroom, not speed. Why:
https://petronellatech.com/blog/dgx-spark-cluster-bandwidth-what-400g-really-means/

**Do I need one cable or two between two units?**
One cable gives you the full 200 Gb/s, because one physical port is two PCIe Gen 5 x4
halves and NCCL uses both. You need both halves **configured** (two interfaces, two
addresses), not two cables. A second cable between the same two units is a second link,
not a faster one, and each unit only has two ports. [01-hardware.md](01-hardware.md).

**Does the same cable work on a Dell, ASUS, MSI, HP, Lenovo, Acer or Gigabyte GB10?**
Yes. Every GB10 system uses the same ConnectX-7 and the same QSFP112 ports. We run four
MSI and two NVIDIA units on one fabric and they measure identically. [01-hardware.md](01-hardware.md).

**Can I mix vendors in one cluster?**
Yes. Our six-node fabric mixes MSI EdgeXpert and DGX Spark Founders Edition units; a
DGX Spark pair and an MSI pair measured 109.27 and 109.31 Gb/s through the switch.
[04-validation.md](04-validation.md). The only practical difference we hit is the
network configuration system (netplan on the DGX Spark, NetworkManager on the MSI).

## Topology

**Can I cluster three units without a switch?**
Yes. NVIDIA's "Connect Three DGX Spark in a Ring Topology" playbook uses three cables,
each unit using both ports. Full pairwise connectivity. Ring kit:
https://petronellatech.com/blog/dgx-spark-cluster-cables-in-stock-0-5m-qsfp112-400g-dac-for-every-gb10-workstation-159-shipped/

**Can I cluster four without a switch?**
Not usefully. Each unit has two ports; four units wired as four point-to-point links
leave two units with no direct path to each other. We built it and confirmed there was
no route between the non-adjacent pair. Four or more means a switch.
[02-two-and-three-nodes.md](02-two-and-three-nodes.md).

**Which switch?**
We use the MikroTik CRS812-8DS-2DQ-2DDQ-RM with QSFP56-DD to 2 x QSFP56 breakout DACs.
One switch serves four nodes on breakouts (six with the native 200G ports); two switches
with a 200G ISL serve eight. [03-switched-fabric.md](03-switched-fabric.md),
[06-bill-of-materials.md](06-bill-of-materials.md).

**Is six on two switches an NVIDIA-supported configuration?**
No. NVIDIA's documented switch playbook covers up to four systems. Six on two switches is
what we run and measure; we describe it as measured, not as supported.

**Does the inter-switch link cost bandwidth?**
Not for one flow: 109.08 Gb/s across the ISL versus 109.31 within one switch. Two 100G
senders sharing one ISL direction split it fairly at 81.9 each. [04-validation.md](04-validation.md).

## Switch configuration

**The breakout cable shows "no link" on the CRS812.**
The QSFP56-DD ports do not auto-negotiate 2 x 200G. Force
`auto-negotiation=no speed=200G-baseCR4` on the lane masters (lanes 1 and 5 of each DD
port). Link comes up in about ten seconds. [03-switched-fabric.md](03-switched-fabric.md).

**Same-switch traffic is fine, cross-switch traffic is slow or jumbo pings fail.**
If both switches uplink to your LAN, RSTP has blocked the ISL and your fabric traffic is
detouring through the LAN at MTU 1500. Raise the RSTP path cost on the second switch's
LAN uplink so the ISL becomes its root port, or remove the second uplink.
[03-switched-fabric.md](03-switched-fabric.md).

**I put the fabric in its own bridge and everything dropped to 5 Gb/s.**
The switch chip hardware-offloads only one bridge; a second bridge is CPU-forwarded. Go
back to one bridge and use VLAN filtering inside it if you need isolation.
[03-switched-fabric.md](03-switched-fabric.md).

**Do I need PFC or ECN?**
We have not. RoCE ran at 196 Gb/s through the switch and at a fair split under ISL
oversubscription with no PFC or ECN configuration. [04-validation.md](04-validation.md).

## Measuring

**My link shows 200G but I only get 12 to 13 Gb/s.**
Two candidates. If that is an `ib_write_bw` number, the NIC is firmware power-throttled
and nothing in the status output will say so; update the OS and firmware and reboot (ours
went 12.74 to 111.86 Gb/s). If that is a single-stream iperf3 number, that is the ARM
CPU, not the link; measure with `ib_write_bw`. [01-hardware.md](01-hardware.md),
[04-validation.md](04-validation.md).

**I get 111 Gb/s. Where is the other half?**
You are driving one PCIe half. Run two `ib_write_bw` pairs, one per RDMA device, and add
them: 98 + 98 = 196. [04-validation.md](04-validation.md).

**What does `packet_seq_err` mean?**
The NIC received a RoCE packet out of sequence: loss or reordering in the path. A few
thousand under deliberate oversubscription with throughput near line rate is congestion
control working. The same counter growing with throughput in the single digits is a
broken path. [04-validation.md](04-validation.md).

## Models

**Will clustering make my model faster?**
Clustering is a capacity play. A single GB10 runs models up to roughly 200B parameters;
two linked run up to 405B. Decode is bound by the 273 GB/s memory bus, which the 25 GB/s
link cannot change. Where tensor parallel does help per-stream speed is on
mixture-of-experts models whose per-rank working set shrinks: Qwen3.8-Flash-Next went
from 35.3 / 36.0 / 53.2 tok/s on two nodes to 39.6 / 57.0 / 76.9 on four with expert
parallel. [01-hardware.md](01-hardware.md), [05-serving-models.md](05-serving-models.md).

**Why does the stock vLLM image fail on a GB10?**
The GPU is `sm_121`, and as of August 2026 the vendor images had the wrong attention
backend gate, a kernel-library NaN, a silent NCCL downgrade, a CUTLASS DSL mismatch and
a PDL race on that capability. The community patch chains fix all five.
[05-serving-models.md](05-serving-models.md).

**Can one model span all six units?**
Not with the checkpoints we tried: tensor parallel 6 fails (16 heads not divisible by 6)
and pipeline parallel fails on the architecture's cross-layer connections. Run pools of
pairs (about 386 tok/s aggregate for six units) or a four-node group plus a pair. Eight
divides cleaner. [05-serving-models.md](05-serving-models.md).

**How do four GB10 units compare to H200s?**
On GLM-5.3-Flash, four GB10 decode at 26.5 to 46.7 tok/s single stream against 233 to
339 on four H200. Roughly one tenth, at a fraction of the cost and power, with a
2.25M-token KV cache. https://petronellatech.com/ai/llm-benchmarks/

**A worker died seven seconds after "GPU KV cache size" with no traceback.**
Check `journalctl -u earlyoom` on that host. Then lower `--gpu-memory-utilization` (0.65
for four-node expert parallel, 0.72 to 0.75 for a single node) and run a memory guard.
[05-serving-models.md](05-serving-models.md).

## Buying

**What does the fabric cost?**
Two nodes $159; three nodes $435; four on one switch $874 in cables and breakouts plus
the switch; six on two switches about $1,311 to $1,470 plus two switches.
[06-bill-of-materials.md](06-bill-of-materials.md).

**Do you ship outside the United States?**
Checkout is United States only. Contact us for a quote elsewhere:
https://petronellatech.com/hardware/dgx-spark-cluster-cable/

## Sources

Each answer cites the document that holds the evidence; those documents carry the
primary sources. NVIDIA: https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html ,
https://build.nvidia.com/spark/connect-two-sparks ,
https://build.nvidia.com/spark/connect-three-sparks .
