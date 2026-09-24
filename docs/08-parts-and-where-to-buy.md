# 08. Parts and where to buy

**Summary.** Every GB10 workstation clusters over the same ConnectX-7 QSFP112 ports, so
the parts list is short: one short QSFP112 passive direct-attach copper (DAC) cable per
link for two or three nodes, and for four or more a 200G-capable switch, breakout DACs
and one node cable per unit. This page lists the parts NVIDIA approves, the other parts
owners report working, and where each one is sold. It is a buyer's reference, not a
recommendation of one seller. Check current stock and pricing with each seller.

## How many cables

| Nodes | Topology | Node cables | Other parts |
|---|---|---|---|
| 2 | Direct, Port 0 to Port 0 | 1 | none |
| 3 | Switchless ring (NVIDIA's documented maximum without a switch) | 3 | none |
| 4 | Switch (NVIDIA's documented switch playbook covers up to four) | 4 | one 200G switch, breakout DACs |
| 5 to 8 | Switch, measured by us, not an NVIDIA-supported configuration | one per node | switch(es), breakout DACs, an inter-switch DAC for two switches |

Three-node ring wiring, from NVIDIA's ring playbook: Node 1 Port 0 to Node 2 Port 1,
Node 2 Port 0 to Node 3 Port 1, Node 3 Port 0 to Node 1 Port 1. Every cable joins a
Port 0 to a Port 1. Details in [02-two-and-three-nodes.md](02-two-and-three-nodes.md).

One cable carries the whole link. The port is two PCIe Gen 5 x4 halves on one wire, and
with both halves configured we measure 196 Gb/s, about 24.5 GB/s, per cable
([04-validation.md](04-validation.md)). A second cable between the same two units adds a
second link, not more speed.

## Node cables

All of these are short passive QSFP DACs for the same port. On a GB10 they link at
200 Gb/s; a 400G rating on the label is headroom, not extra speed
([01-hardware.md](01-hardware.md)).

| Part | Length | Status | Where it is sold |
|---|---|---|---|
| Amphenol NJAAKK-N911 | 400 mm | NVIDIA-approved ("QSFP to QSFP112, 32AWG, 400mm, LSZH" in the DGX Spark user guide) | Distributors; also the part number on NVIDIA's own stacking-cable listings |
| Amphenol NJAAKK0006 | 0.5 m | NVIDIA-approved (the guide calls it the 0.5 m version of NJAAKK-N911) | Distributors |
| Luxshare LMTQF022-SD-R | 400 mm | NVIDIA-approved ("QSFP112 400G DAC Cable, 400mm, 30AWG") | Distributors |
| NVIDIA Marketplace "QSFP Cable 0.4m for DGX Spark" | 0.4 m | The cable NVIDIA's clustering playbooks link | NVIDIA Marketplace |
| Lenovo 4X91U42988 (ThinkStation PGX QSFP Link Cable) | 0.4 m | Lenovo first-party; owners on the NVIDIA developer forum report full-rate links between GB10 units | Lenovo.com and resellers such as CDW, Connection and AVADirect. Forum buyers in August 2026 reported orders shipping from overseas in one to two weeks |
| Amphenol NJAAKR-0006 | 0.5 m | Same Amphenol QSFP112 family; owners report full-rate links | DigiKey, which forum members report ships internationally |

In the United States, Petronella Technology Group, Inc. (the maintainer of this guide)
stocks a 0.5 m QSFP112 passive DAC to the NJAAKK0006 / LMTQF022-SD-R specification and
ships it in 1 to 3 business days:
[DGX Spark and GB10 cluster cable](https://petronellatech.com/hardware/dgx-spark-cluster-cable/).
The same cable fits every GB10 chassis; these pages carry the fit notes for each one:

- [ASUS Ascent GX10 cluster cable](https://petronellatech.com/hardware/asus-gx10-cluster-cable/)
- [Dell Pro Max with GB10 cluster cable](https://petronellatech.com/hardware/dell-pro-max-gb10-cluster-cable/)
- [MSI EdgeXpert cluster cable](https://petronellatech.com/hardware/msi-edgexpert-cluster-cable/)
- [HP ZGX Nano cluster cable](https://petronellatech.com/hardware/hp-zgx-nano-cluster-cable/)
- [Lenovo ThinkStation PGX cluster cable](https://petronellatech.com/hardware/lenovo-thinkstation-pgx-cluster-cable/)
- [Acer Veriton GN100 cluster cable](https://petronellatech.com/hardware/acer-veriton-gn100-cluster-cable/)
- [Gigabyte AI TOP ATOM cluster cable](https://petronellatech.com/hardware/gigabyte-ai-top-atom-cluster-cable/)

How to choose: all of the cables above fit the same port, so choose on length and timing.
The 0.4 m parts suit units stacked directly on each other; 0.5 m gives a few more inches
for side-by-side units and for the longest run in a three-node ring. Outside the United
States, or with no deadline, the Lenovo part is a sensible low-cost route.

## Switch and switch cables (four nodes or more)

| Part | What it does | Notes |
|---|---|---|
| MikroTik CRS812-8DS-2DQ-2DDQ-RM | 2 x 400G QSFP56-DD, 2 x 200G QSFP56, 8 x 50G SFP56 | What we run. Each DD port breaks out to 2 x 200G, so one switch serves four nodes on breakouts, six with the native 200G ports. See [03-switched-fabric.md](03-switched-fabric.md) |
| MikroTik CRS804 | 200G switch that other GB10 owners use | Often out of stock in 2026; we have no measurements on it |
| QSFP56-DD to 2 x QSFP56 breakout DAC (we used NADDOD Q2Q56-400G-CU1, MikroTik-coded) | Two nodes per DD port | The DD end does not auto-negotiate; force 200G-baseCR4 on the lane masters |
| 200G QSFP56 DAC | Inter-switch link for two switches | A spare QSFP112 node cable worked for us; MikroTik does not vendor-lock DACs |

Quantities and a fabric budget by node count are in
[06-bill-of-materials.md](06-bill-of-materials.md).

## Before you buy more hardware

Most "slow cluster" reports are configuration, not parts: a link that needs a firmware
update or a full power drain, MTU 1500 somewhere in the path, a second bridge on the
switch, or a test that only uses one PCIe half. Run the checks in
[04-validation.md](04-validation.md) first.

## Sources

- NVIDIA DGX Spark User Guide, ConnectX-7 Networking (approved cables, 200 Gb/s per port, direct up to three systems, switch up to four): https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html
- NVIDIA, Connect Three DGX Spark in a Ring Topology (port-by-port ring wiring): https://build.nvidia.com/spark/connect-three-sparks
- NVIDIA developer forum, owner reports on the Lenovo 4X91U42988 and Amphenol NJAAKR-0006 (August and September 2026): https://forums.developer.nvidia.com/t/381031 , https://forums.developer.nvidia.com/t/362679 , https://forums.developer.nvidia.com/t/362403
- Our measurements and purchase notes, 2026-08-15 to 2026-08-31 ([04-validation.md](04-validation.md), [06-bill-of-materials.md](06-bill-of-materials.md))
