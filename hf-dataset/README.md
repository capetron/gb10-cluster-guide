---
license: cc-by-4.0
pretty_name: GB10 cluster bandwidth benchmark
task_categories:
  - other
tags:
  - gb10
  - dgx-spark
  - connectx-7
  - networking
  - benchmark
  - rdma
  - roce
size_categories:
  - n<1K
---

# GB10 cluster bandwidth benchmark

Measured RDMA and TCP bandwidth between NVIDIA GB10 Grace Blackwell workstations (NVIDIA
DGX Spark and MSI EdgeXpert MS-C931) over their ConnectX-7 QSFP112 ports: one direct 0.5 m
QSFP112 400G passive DAC, one MikroTik 200G switch, and two switches joined by a 200G
inter-switch link, up to six nodes concurrently. Fifteen rows, each with the tool, the
exact flags, the result in Gb/s and the component figures.

Headline rows: 111.86 Gb/s on one PCIe half of a port and 196.08 Gb/s with both halves on
a single cable (98 percent of the 200 Gb/s line rate); 109.11 Gb/s per half through a
switch; 327.4 Gb/s aggregate across three concurrent pairs on two switches; and the two
misconfigurations that drop the same links to under 5 Gb/s.

## Files

- `gb10-cluster-bandwidth-2026.csv`: the data (columns documented in `README.md` of the
  source repository's `data/` directory)

## Source and method

The dataset is extracted from the public guide
https://github.com/capetron/gb10-cluster-guide (chapter `docs/10-benchmark-data.md`
collects the tables; `docs/04-validation.md` has the method, the GID lookup, and the
counters to read). Measurements were taken 2026-08-15, 2026-08-28 and 2026-08-31 by
Petronella Technology Group, Inc. on hardware it owns. The node cable in every row is the
Amphenol NJAAKR-0006 (0.5 m, 30 AWG), built to the Amphenol NJAAKK0006 / Luxshare
LMTQF022-SD-R specification that NVIDIA's DGX Spark user guide lists.

## Citation

Petronella Technology Group, Inc. (2026). GB10 cluster bandwidth benchmark.
https://github.com/capetron/gb10-cluster-guide/blob/main/docs/10-benchmark-data.md

## Licence

CC BY 4.0. Reproduce a row and get a different number? Open an issue on the source
repository with your command line and raw output.
