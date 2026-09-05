# 01. The hardware: GB10 variants, the ConnectX-7 port, and the cable

**Summary.** Every GB10 workstation, regardless of the badge on the front, ships the same
NVIDIA GB10 Grace Blackwell system-on-chip, 128 GB of unified LPDDR5x memory on a 256-bit
bus at 4266 MHz delivering 273 GB/s, and a ConnectX-7 network controller exposed as two
QSFP ports on the rear panel. NVIDIA documents each port at up to 200 Gb/s, and the reason
is structural: the ConnectX-7 is fed by two independent PCIe Gen 5 x4 links, so each
physical port appears in Linux as two network interfaces and two RDMA devices, each good
for roughly 100 Gb/s. The approved direct-attach cable is a QSFP112 part rated for 400G;
it negotiates at 200G on this NIC, and the extra rating is headroom, not speed you get.
This document lists the variants we know of, explains the two-halves port model that every
later document depends on, and puts the 25 GB/s link next to the 273 GB/s memory bus so
the rest of the guide makes sense.

## The GB10 variants

All of these are GB10 Grace Blackwell systems with 2 x QSFP112 on a ConnectX-7 NIC. The
cluster cable and every procedure in this guide apply to all of them. We have run four
MSI units and two DGX Spark Founders Edition units side by side on the same switched
fabric; a DGX Spark pair and an MSI pair measured within 0.1 Gb/s of each other through
the switch (109.27 versus 109.31 Gb/s, see [04-validation.md](04-validation.md)).

| System | Notes from our use |
|---|---|
| NVIDIA DGX Spark (Founders Edition) | Ships with netplan (systemd-networkd) network configuration. Our two are on the second switch. |
| MSI EdgeXpert MS-C931 | Ships with NetworkManager. Our four are on the first switch. No BMC; a physical power button is the only remote-power fallback, which drives the memory-guard advice in [05-serving-models.md](05-serving-models.md). |
| ASUS Ascent GX10 | Same NIC and ports. |
| Dell Pro Max with GB10 | Same NIC and ports. |
| HP ZGX Nano G1n | Same NIC and ports. |
| Lenovo ThinkStation PGX | Same NIC and ports. |
| Acer Veriton GN100 | Same NIC and ports. |
| Gigabyte AI TOP ATOM | Same NIC and ports. |

Vendor-specific cable pages, if you want the one for your box:
[ASUS GX10](https://petronellatech.com/hardware/asus-gx10-cluster-cable/),
[Dell Pro Max GB10](https://petronellatech.com/hardware/dell-pro-max-gb10-cluster-cable/),
[MSI EdgeXpert](https://petronellatech.com/hardware/msi-edgexpert-cluster-cable/),
[HP ZGX Nano](https://petronellatech.com/hardware/hp-zgx-nano-cluster-cable/),
[Lenovo ThinkStation PGX](https://petronellatech.com/hardware/lenovo-thinkstation-pgx-cluster-cable/),
[Acer Veriton GN100](https://petronellatech.com/hardware/acer-veriton-gn100-cluster-cable/),
[Gigabyte AI TOP ATOM](https://petronellatech.com/hardware/gigabyte-ai-top-atom-cluster-cable/).

## The ConnectX-7 port, as Linux sees it

NVIDIA's DGX Spark user guide states the facts plainly and they govern everything else:

- Two QSFP ports per device, "up to 200 Gigabits per second (Gb/s)" each, Ethernet
  configuration only. The left port (closest to the RJ45 port) is Port 0; the right
  port is Port 1.
- The ConnectX-7 connects to the Grace Blackwell SoC over "two independent PCIe Gen 5 x4
  links". Each QSFP port therefore maps to two PCIe addresses, in PCIe domain 0000 and
  PCIe domain 0002.
- Each QSFP port produces four Linux interfaces. For Port 0: `enp1s0f0np0` and
  `enP2p1s0f0np0` (Ethernet) plus `rocep1s0f0` and `roceP2p1s0f0` (RDMA). For Port 1:
  `enp1s0f1np1`, `enP2p1s0f1np1`, `rocep1s0f1`, `roceP2p1s0f1`.

The consequence is easy to state and easy to forget: **`enp1s0f0np0` and `enP2p1s0f0np0`
are the same wire.** They are two PCIe halves of one physical port. One half carries about
100 Gb/s. To see 200 Gb/s on one cable you need traffic on both halves at once. NCCL does
this on its own when you hand it both RDMA devices; a single TCP stream or a single
`ib_write_bw` process does not.

Our measurements on a direct cable between two units (see [04-validation.md](04-validation.md)
for the commands):

| Path | ib_write_bw, --report_gbits |
|---|---|
| One half (one RDMA device) | 111.86 Gb/s |
| Both halves concurrently | 98.04 + 98.04 = 196.08 Gb/s |

That 196 Gb/s is 98 percent of the 200 Gb/s line rate. Field reports we have seen from
other GB10 owners land at 185 to 190 Gb/s dual-port, in the same band.

A related trap: because both halves share one wire, LLDP on the second half can look like
a self-loop. It is not a wiring fault.

## Why the cable says 400G and the link says 200G

NVIDIA's approved cables for the DGX Spark QSFP ports are:

- Amphenol NJAAKK-N911 (QSFP to QSFP112, 32 AWG, 400 mm, LSZH)
- Amphenol NJAAKK0006 (the 0.5 m version)
- Luxshare LMTQF022-SD-R (QSFP112 400G DAC, 400 mm, 30 AWG)

All three are QSFP112 passive direct-attach copper parts rated for 400G. The DGX Spark's
ConnectX-7 negotiates them at 200 Gb/s, which is the port's documented ceiling. The 400G
rating is the cable's capability, not the link's; the same cable on a 400G NIC would run at
400G. On a GB10 it buys nothing beyond headroom and compatibility. It also means a
"200G" cable is not required; what is required is a QSFP112 form factor that the NIC
recognizes. The cable we sell is the NJAAKK0006 / LMTQF022-SD-R spec in 0.5 m, 32 AWG:
https://petronellatech.com/hardware/dgx-spark-cluster-cable/ . A longer write-up of the
bits-versus-bytes arithmetic is at
https://petronellatech.com/blog/dgx-spark-cluster-bandwidth-what-400g-really-means/ .

In practice the 0.5 m length covers side-by-side or stacked units. Separated by a monitor
you want 1 m; across two shelves, 2 m; across a small rack, 3 m (active copper at that
length).

## 273 GB/s inside, 25 GB/s outside

The GB10's unified memory delivers 273 GB/s. The interconnect, at 200 Gb/s, delivers
25 GB/s before protocol overhead (200 divided by 8), and about 23 to 24 GB/s after it.
So local memory is roughly eleven times faster than the fastest path to the next node.

This single ratio explains most of what you will see in [05-serving-models.md](05-serving-models.md):

- Decode on a single GB10 is memory-bandwidth bound. On one unit we measured a dense
  27B FP8 model at 8.3 tokens per second decode against 1,963 tokens per second prefill,
  and the decode figure lands within 12 percent of the pure bandwidth prediction
  (273 GB/s divided by 29 GB of weights is 9.4 tokens per second).
- Clustering is a capacity play, not a raw speed boost. A single unit runs models up to
  roughly 200B parameters; two linked units run up to 405B. Tensor parallel across the
  fabric adds memory and can add per-stream speed when the model is a mixture of experts
  whose active parameters shrink per rank, but it does not turn 25 GB/s into 273 GB/s.
- The fabric is rarely the limiter once it is running at line rate. During a four-node
  GLM-5.3-Flash run, 17 GB crossed the RDMA device; during a two-node Qwen3.8-Flash-Next
  run, 11 GB. Those are collectives, not the bottleneck. When the fabric is not at line
  rate (a throttled NIC, a CPU-forwarded bridge, a blocked ISL detouring over 2.5G
  copper), it becomes the only thing that matters.

## Things that hide

Two faults we hit are invisible in every status output and only show in a bandwidth
measurement:

1. **A firmware power-throttled ConnectX-7.** One of our units reported 12.74 Gb/s RDMA on a
   link that showed 200G, RS-FEC, PCIe Gen5 x4, and "No issue was observed" in `mstlink`.
   A full OS upgrade plus reboot took it to 111.86 Gb/s, an 8.8x change. The public
   version of this story is the driver update from 580.142 to 580.159.03 that turned
   13 Gb/s into 111.86 Gb/s. Re-measure after any rebuild.
2. **A single TCP stream on the GB10's ARM cores.** A single iperf3 stream sits near
   12 Gb/s no matter what the link is doing, which is numerically almost identical to the
   throttled RDMA figure above. That coincidence is how the throttle hid for weeks. Use
   `ib_write_bw` as the authority for link health; treat single-stream iperf3 as a CPU
   benchmark.

## Sources

- NVIDIA DGX Spark User Guide, ConnectX-7 Networking: https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html
  (port count, 200 Gb/s per port, approved cables, two PCIe Gen 5 x4 links, interface names, direct up to 3, switched up to 4)
- NVIDIA, Connect Two Sparks: https://build.nvidia.com/spark/connect-two-sparks
- Petronella Technology Group, Inc., DGX Spark cluster cable: https://petronellatech.com/hardware/dgx-spark-cluster-cable/
  (variant list, cable spec, 400G-rated / 200G link, "capacity play, not a raw speed boost")
- Petronella Technology Group, Inc., DGX Spark memory bandwidth, 273 GB/s, and what 400G adds:
  https://petronellatech.com/blog/dgx-spark-cluster-bandwidth-what-400g-really-means/
  (128 GB LPDDR5x 256-bit 4266 MHz 273 GB/s, 13 to 111.86 Gb/s driver story, 185 to 190 Gb/s field reports, 200B / 405B model capacity, 25 GB/s arithmetic)
- Our measurements, 2026-08-15 (111.86 / 196.08 Gb/s, 12.74 Gb/s throttle, 1,963 / 8.3 tok/s single node, 12 Gb/s single-stream TCP) and 2026-08-28 / 2026-08-31 (switched fabric); see [04-validation.md](04-validation.md)
