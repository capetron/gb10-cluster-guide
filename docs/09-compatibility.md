# 09. Cable compatibility by part number and by GB10 model

**Summary.** Every GB10 workstation uses the same ConnectX-7 QSFP112 port, so the same
short QSFP112 passive DAC fits all of them. This page lists each cable part number we know
of, what NVIDIA or the vendor says about it, and what owners report, then gives the fit
notes per GB10 model. It states only what a source supports. Part numbers are not treated
as interchangeable unless a source says so.

## Part numbers

| Part | Length | AWG | What the source says | Source |
|---|---|---|---|---|
| Amphenol NJAAKK-N911 | 400 mm | 32 | Listed as NVIDIA-approved in the DGX Spark user guide | NVIDIA DGX Spark User Guide, ConnectX-7 Networking |
| Amphenol NJAAKK0006 | 0.5 m | n/a | Listed as NVIDIA-approved (the 0.5 m version of NJAAKK-N911) | same |
| Luxshare LMTQF022-SD-R | 400 mm | 30 | Listed as NVIDIA-approved | same |
| NVIDIA Marketplace "QSFP Cable 0.4m for DGX Spark" | 0.4 m | n/a | The cable NVIDIA's clustering playbooks link | NVIDIA Marketplace |
| Lenovo 4X91U42988 | 0.4 m | n/a | Lenovo first-party link cable; owners report full-rate links between GB10 units | NVIDIA developer forum threads 381031, 362679 |
| Amphenol NJAAKR-0006 | 0.5 m | 30 | Same Amphenol QSFP112 family. Not on NVIDIA's list by this part number. Owners report full-rate links | NVIDIA developer forum thread 362403; distributor listings |

Notes:

- NJAAKR-0006 is the part Petronella Technology Group, Inc. stocks. We do not claim it is
  the same part as NJAAKK0006 or LMTQF022-SD-R. We say it is a 0.5 m, 30 AWG cable in the
  same Amphenol QSFP112 family, built for the same port.
- We measured 196.08 Gb/s (98.04 + 98.04, both PCIe halves active) on a direct cable and
  recorded the cable module data with `gb10-cluster-check`. One measurement on one
  cable is not a certification; see [04-validation.md](04-validation.md) for the method.
- A 400G rating on a label is headroom. A GB10 port links at 200 Gb/s
  ([01-hardware.md](01-hardware.md)).

## By GB10 model

| Model | Port | Cable | Fit notes page |
|---|---|---|---|
| NVIDIA DGX Spark Founders Edition | ConnectX-7 QSFP112 | Any cable in the table above | [DGX Spark and GB10 cluster cable](https://petronellatech.com/hardware/dgx-spark-cluster-cable/) |
| ASUS Ascent GX10 | same | same | [ASUS Ascent GX10 cluster cable](https://petronellatech.com/hardware/asus-gx10-cluster-cable/) |
| Dell Pro Max with GB10 | same | same | [Dell Pro Max GB10 cluster cable](https://petronellatech.com/hardware/dell-pro-max-gb10-cluster-cable/) |
| MSI EdgeXpert | same | same | [MSI EdgeXpert cluster cable](https://petronellatech.com/hardware/msi-edgexpert-cluster-cable/) |
| HP ZGX Nano | same | same | [HP ZGX Nano cluster cable](https://petronellatech.com/hardware/hp-zgx-nano-cluster-cable/) |
| Lenovo ThinkStation PGX | same | same (Lenovo sells its own 4X91U42988) | [Lenovo ThinkStation PGX cluster cable](https://petronellatech.com/hardware/lenovo-thinkstation-pgx-cluster-cable/) |
| Acer Veriton GN100 | same | same | [Acer Veriton GN100 cluster cable](https://petronellatech.com/hardware/acer-veriton-gn100-cluster-cable/) |
| Gigabyte AI TOP ATOM | same | same | [Gigabyte AI TOP ATOM cluster cable](https://petronellatech.com/hardware/gigabyte-ai-top-atom-cluster-cable/) |

We ran four MSI EdgeXpert MS-C931 and two DGX Spark Founders Edition units. We did not
test the other models ourselves; the shared chip and port come from NVIDIA's GB10
documentation and each vendor's specification.

## Choosing a length

0.4 m suits units stacked directly on each other. 0.5 m adds a few inches for
side-by-side units and for the longest run in a three-node ring. Four or more nodes need a
switch ([03-switched-fabric.md](03-switched-fabric.md)).

## Where to buy

See [08-parts-and-where-to-buy.md](08-parts-and-where-to-buy.md) for every seller we know
of. In the United States, Petronella Technology Group, Inc. sells the NJAAKR-0006 and ships
in 1 to 3 business days: [the cable hub](https://petronellatech.com/hardware/dgx-spark-cluster-cable/).
Our measured benchmark tables for these clusters are at
[petronellatech.com/ai/llm-benchmarks/](https://petronellatech.com/ai/llm-benchmarks/).

## Sources

- NVIDIA DGX Spark User Guide, ConnectX-7 Networking: https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html
- NVIDIA, Connect Three DGX Spark in a Ring Topology: https://build.nvidia.com/spark/connect-three-sparks
- NVIDIA developer forum owner reports: https://forums.developer.nvidia.com/t/381031 , https://forums.developer.nvidia.com/t/362679 , https://forums.developer.nvidia.com/t/362403
- Our measurements: [04-validation.md](04-validation.md)
