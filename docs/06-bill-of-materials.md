# 06. Bill of materials

**Summary.** For two units you need one cable. For three, three cables. For four or
more you need one 200G-capable switch, one QSFP56-DD to 2 x QSFP56 breakout DAC per pair
of nodes, and one node cable per unit; for two switches add one 200G DAC for the
inter-switch link. This is what we bought, with the prices we paid or list at
publication, and what we would budget. Every GB10 variant uses the same QSFP112 port
and the same cable.

## Cables

The cluster cable is a 0.5 m (about 19 in) QSFP112 passive direct-attach copper cable,
32 AWG, to the NVIDIA-approved Amphenol NJAAKK0006 / Luxshare LMTQF022-SD-R
specification. It is rated 400G and links at 200G on every GB10 (see
[01-hardware.md](01-hardware.md)). One cable per node in every topology below.

| Item | Qty for 2 nodes | Qty for 3 nodes (ring) | Qty for N nodes on a switch | Price |
|---|---|---|---|---|
| Single cable | 1 | | | $159 |
| 2-pack | | | pairs | $299 ($149.50 each) |
| 3-pack ring kit | | 1 | | $435 ($145 each) |

Free shipping inside the United States; United States addresses only; in stock and
ships in 1 to 3 business days; 30-day compatibility guarantee. Volume pricing for five or
more by phone, 919-348-4912.

- Single and bundles: https://petronellatech.com/hardware/dgx-spark-cluster-cable/
- Ring kit page with the quick-spec and alternative-length tables:
  https://petronellatech.com/blog/dgx-spark-cluster-cables-in-stock-0-5m-qsfp112-400g-dac-for-every-gb10-workstation-159-shipped/

Longer lengths (1 m for units separated by a monitor, 2 m for two shelves, 3 m active
copper across a small rack) are built to order through the same page.

Vendor-specific pages, same cable: [ASUS Ascent GX10](https://petronellatech.com/hardware/asus-gx10-cluster-cable/),
[Dell Pro Max GB10](https://petronellatech.com/hardware/dell-pro-max-gb10-cluster-cable/),
[MSI EdgeXpert](https://petronellatech.com/hardware/msi-edgexpert-cluster-cable/),
[HP ZGX Nano](https://petronellatech.com/hardware/hp-zgx-nano-cluster-cable/),
[Lenovo ThinkStation PGX](https://petronellatech.com/hardware/lenovo-thinkstation-pgx-cluster-cable/),
[Acer Veriton GN100](https://petronellatech.com/hardware/acer-veriton-gn100-cluster-cable/),
[Gigabyte AI TOP ATOM](https://petronellatech.com/hardware/gigabyte-ai-top-atom-cluster-cable/).

## Switch

**MikroTik CRS812-8DS-2DQ-2DDQ-RM**, RouterOS 7.24.1 at the time of our build.

Ports: 2 x 400G QSFP56-DD, 2 x 200G QSFP56, 8 x 50G SFP56, 2 x 10G RJ45. Each QSFP56-DD
port breaks out to 2 x 200G, so:

| Nodes | Switches | How |
|---|---|---|
| 4 | 1 | Both DD ports broken out (4 x 200G legs). Native QSFP56 ports free. |
| 5 to 6 | 1 | Both DD ports broken out plus the two native QSFP56 ports (no ISL needed). |
| 5 to 8 | 2 | Both DD ports broken out on each switch (8 legs), native QSFP56 ports for the ISL. This is our layout, populated with six. |

Configuration: forced 200G-baseCR4 on the DD lane masters, l2mtu 9216, one
hardware-offloaded bridge, and the RSTP handling in [03-switched-fabric.md](03-switched-fabric.md).
Check current MikroTik pricing; we do not quote it here.

Why this switch: it was the one with a public report of the 2 x 200G DD breakout working
against GB10 units specifically, its port mix gives four 200G legs plus two more 200G
ports in one rack unit, and it does not vendor-lock optics or DACs. NVIDIA's documented
switch playbook covers up to four systems; we run six across two switches as described.

## Breakout and ISL cables

| Item | Qty | Price we paid | Notes |
|---|---|---|---|
| NADDOD Q2Q56-400G-CU1, QSFP-DD to 2 x QSFP56 breakout DAC, MikroTik-coded | 1 per DD port (2 per fully-used switch); we bought 4 for two switches and kept 1 spare | $138 each | The node's 0.5 m QSFP112 cable plugs into one QSFP56 leg. The DD end does not auto-negotiate: force 200G-baseCR4 on the lane masters. |
| QSFP56 200G DAC for the ISL | 1 per switch pair | | We reused a cable freed from the direct-attach links (the same QSFP112 DAC works, MikroTik does not vendor-lock). Force 200G-baseCR4 on both ends. |

A 0.5 m ISL cable assumes the two switches are adjacent in the rack. Budget a longer
QSFP56 DAC if they are not.

## Per-node

Each GB10 unit needs one cluster cable and nothing else on the fabric side. On the
management side we run each unit's RJ45 port to an ordinary copper switch; note that
some copper switches advertise only 100/1000/2500BASE-T, so a unit that negotiated 10G
elsewhere will land at 2.5G. It does not affect the fabric.

For reference, list prices we observed for 4 TB Gen5 SSD configurations while shopping
for additional units in June 2026 (new, not refurbished; check current pricing):
Gigabyte AI TOP ATOM $3,999; ASUS Ascent GX10 about $4,149; NVIDIA DGX Spark Founders
Edition $4,699; MSI EdgeXpert MS-C931 about $4,000. All GB10 units share the same chip and
a software power cap, so raw performance is essentially equal; the differences are
cooling and sustained-load behavior.

## What to budget

Fabric only, excluding the nodes and the switch itself:

| Topology | Cables | Breakouts | ISL | Fabric total (cables and DACs) |
|---|---|---|---|---|
| 2 nodes, direct | 1 x $159 | | | $159 |
| 3 nodes, ring | 3-pack $435 | | | $435 |
| 4 nodes, one switch | 2 x 2-pack $598 | 2 x $138 | | $874 plus switch |
| 6 nodes, two switches | 3 x 2-pack $897 | 3 x $138 | 1 DAC (reused or about $159) | $1,311 to $1,470 plus two switches |
| 8 nodes, two switches | 4 x 2-pack $1,196 | 4 x $138 | 1 DAC | $1,748 to $1,907 plus two switches |

Everything above the three-node ring also needs rack space, power for the switch, and a
few hours to validate the fabric before trusting it ([04-validation.md](04-validation.md)).
Two things we did not buy and now recommend for anyone racking GB10 units remotely: a
smart PDU (the units have no BMC, so a wedged unit needs a physical or PDU power cycle)
and a memory guard on every serving rank ([05-serving-models.md](05-serving-models.md)).

## Sources

- Petronella Technology Group, Inc., cable hub and ring-kit pages (prices, pack sizes, shipping terms, cable spec, alternative lengths):
  https://petronellatech.com/hardware/dgx-spark-cluster-cable/ ,
  https://petronellatech.com/blog/dgx-spark-cluster-cables-in-stock-0-5m-qsfp112-400g-dac-for-every-gb10-workstation-159-shipped/
- NVIDIA DGX Spark User Guide, ConnectX-7 Networking (approved cable part numbers; switch playbook up to four systems): https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html
- MikroTik CRS812-8DS-2DQ-2DDQ-RM product documentation (port inventory)
- Our purchase notes, 2026-08-17 (switch model and quantity, breakout part number and price, wiring plan, ISL cable reuse), 2026-06-19 (GB10 unit list prices), 2026-08-31 (2.5G copper management uplinks)
