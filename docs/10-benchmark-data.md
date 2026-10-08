# 10. Benchmark data: every number in this guide, in one place

**Summary.** This chapter gathers every bandwidth and serving measurement that appears
elsewhere in the guide into tables you can cite, with the command line beside each
figure, the dates we ran them, and a machine-readable copy in
[data/gb10-cluster-bandwidth-2026.csv](../data/gb10-cluster-bandwidth-2026.csv). Nothing
here is new; it is the same data as [04-validation.md](04-validation.md),
[03-switched-fabric.md](03-switched-fabric.md) and [05-serving-models.md](05-serving-models.md),
collected so that a reader, a journalist or an AI assistant can quote one source. If a
number here ever disagrees with a chapter, the chapter wins and this page has a bug:
open an issue.

## What was measured, and on what

| Item | Value |
|---|---|
| Nodes | Six NVIDIA GB10 Grace Blackwell workstations: two NVIDIA DGX Spark, four MSI EdgeXpert MS-C931 (the same ConnectX-7 NIC and QSFP112 ports in every unit) |
| Node cable | 0.5 m QSFP112 400G passive DAC, Amphenol NJAAKR-0006, 30 AWG, built to the NVIDIA-listed Amphenol NJAAKK0006 / Luxshare LMTQF022-SD-R specification |
| Switches | Two MikroTik CRS812-8DS-2DQ-2DDQ-RM, QSFP56-DD ports broken out to 2 x 200G, one 200G DAC as the inter-switch link (ISL) |
| Link | 200 Gb/s per QSFP112 port, two PCIe Gen 5 x4 halves per port, RoCE v2, MTU 9000, no PFC, no ECN |
| Bandwidth tool | `ib_write_bw` from `perftest`, `--report_gbits`; `iperf3` only as a TCP sanity check |
| NIC driver | the direct-cable figures were taken after the driver update from 580.142 to 580.159.03 ([01-hardware.md](01-hardware.md)); other firmware and OS versions were not recorded in the logs |
| Dates | 2026-08-15 (direct cable), 2026-08-28 (through one switch, serving), 2026-08-31 (six-node matrix, switch traps) |

## Table 1. Direct cable, two units, no switch (2026-08-15)

| Measurement | Result | Command |
|---|---|---|
| One PCIe half, RDMA write | 111.86 Gb/s | `ib_write_bw -d rocep1s0f0 -x 3 -F -q 8 -s 1048576 -D 10 --report_gbits <peer>` |
| Both halves concurrently | 98.04 + 98.04 = 196.08 Gb/s (98 percent of the 200 Gb/s line rate) | the same command on `rocep1s0f0` and `roceP2p1s0f0` at once, results added |
| One half on a firmware power-throttled NIC, before the OS and driver update | 12.74 Gb/s | same as row 1; the link showed 200G, RS-FEC, PCIe Gen5 x4 and a clean `mstlink` while delivering this |
| Single TCP stream, `iperf3` | about 12 Gb/s regardless of link | `iperf3 -c <peer>`; this measures the ARM cores, not the fabric |

## Table 2. Through one switch (2026-08-28)

| Measurement | Result | Command |
|---|---|---|
| MSI pair, both halves, traffic crossing the switch ASIC (different DD ports) | 98.0 + 98.0 = 196 Gb/s | `ib_write_bw -d <hca> -x 3 -F -D 6 -s 65536 --report_gbits <peer>` on each half at once |
| MSI pair, `iperf3` TCP on both halves | 93.1 + 92.6 Gb/s | `iperf3 -c <peer>` per half |
| DGX Spark pair through switch B, one half | 109.11 Gb/s (direct-cable baseline 111.86) | the 65,536 B, 6 s command above |
| Switch penalty per half | about 0.75 Gb/s, 0.7 percent | difference of the two rows above |

## Table 3. Six nodes, two switches, concurrent pairs (2026-08-31)

All rows: `ib_write_bw -d <hca> -x 3 -F -D 6 -s 65536 --report_gbits`, one half per pair,
every client launched in the same second, pairs listed client to server.

| Round | Pairs | Result, Gb/s |
|---|---|---|
| R1, three intra-switch pairs | gb10-01 to gb10-02; gb10-03 to gb10-04; gb10-05 to gb10-06 | 109.31 + 109.22 + 109.27 = 327.8 aggregate |
| R2a, one cross-switch flow over the ISL | gb10-05 to gb10-01 | 109.08 (no measurable ISL penalty) |
| R2b, two same-direction cross-switch flows plus one intra | gb10-05 to gb10-01; gb10-06 to gb10-02; gb10-03 to gb10-04 | 81.92 + 81.90 = 163.8 on the 200G ISL (fair split), plus 109.13 intra |
| R3, bidirectional ISL plus one intra | gb10-05 to gb10-01; gb10-02 to gb10-06; gb10-03 to gb10-04 | 109.19 + 109.10 + 109.14 = 327.4 aggregate |

`packet_seq_err` on the sending NICs grew by about 5,500 during R2b only (DCQCN
congestion feedback under a full ISL direction) and by zero in R1, R2a and R3.

## Table 4. Misconfigurations we measured on the way (2026-08-31)

| Condition | Result | Fixed by |
|---|---|---|
| ISL blocked by RSTP, fabric detouring over the campus LAN at MTU 1500 | 4.47 Gb/s cross-switch (2.5 Gb/s campus path) | raising the RSTP path cost of the second switch's campus uplink; 109.08 Gb/s after |
| Fabric moved into a second bridge on the switch (CPU-forwarded) | DGX Spark pair 109 to 4.9 Gb/s; MSI pair both halves 196 to 4.85 Gb/s; iperf3 93 to 8.8 Gb/s | reverting to one hardware-offloaded bridge; 109.2 / 109.3 Gb/s re-verified |

## Table 5. Serving results that depend on the fabric (2026-08-28)

| Measurement | Result |
|---|---|
| GLM-5.3-Flash NVFP4, tensor parallel 4, decode (prose / code / math) | 26.5 / 38.1 / 46.7 tok/s |
| GLM-5.3-Flash NVFP4, TP4, prefill (warm) | 3,840 tok/s, time to first token 2.3 s at 8.9k tokens |
| GLM-5.3-Flash NVFP4, TP4, KV cache | 2,246,948 tokens (16 GiB fp8 per rank) |
| Qwen3.8-Flash-Next NVFP4, TP4 + expert parallel, decode | 39.6 / 57.0 / 76.9 tok/s |
| Qwen3.8-Flash-Next NVFP4, TP4 + expert parallel, six streams | 167.4 tok/s aggregate |
| Six nodes as three TP2 pairs, pool aggregate | about 386 tok/s decode, about 9,450 tok/s prefill |
| RDMA bytes on `rocep1s0f0` of the head node during a four-node GLM-5.3-Flash run | 17 GB (11 GB during a two-node Qwen3.8-Flash-Next run) |

Method and caveats for these rows are in [05-serving-models.md](05-serving-models.md).

## How to reproduce the bandwidth rows

1. Cable and validate the nodes with the read-only health check:
   `./gb10-cluster-check --peer <half-A address> --peer <half-B address>` (see
   [04-validation.md](04-validation.md#health-check-tool)).
2. Start the server detached on the receiving node, or it dies with your SSH session:
   `ssh <node> 'sh -c "nohup ib_write_bw -d rocep1s0f0 -x 3 -F -D 6 -s 65536 --report_gbits </dev/null >/tmp/ibw.log 2>&1 &"'`
3. Run the client: `ib_write_bw -d rocep1s0f0 -x 3 -F -D 6 -s 65536 --report_gbits <peer address>`.
4. For the both-halves figure, run a second server and client pair on `roceP2p1s0f0` against
   the half-B address at the same time and add the two results.
5. Look up the GID index per half (`-x`) with the loop in
   [04-validation.md](04-validation.md#finding-the-rdma-device-and-gid-index); it was 3 on
   every half we own, and it is not guaranteed to be 3 on yours.

## How to cite

The data is CC BY 4.0, like the rest of this guide. Suggested citation:

> Petronella Technology Group, Inc. (2026). GB10 cluster bandwidth benchmark: direct-cable,
> single-switch and two-switch RoCE measurements on six NVIDIA GB10 workstations.
> https://github.com/capetron/gb10-cluster-guide/blob/main/docs/10-benchmark-data.md
> (data: data/gb10-cluster-bandwidth-2026.csv). Accessed <date>.

If you reproduce a row and get a different number, open an issue with your command line
and raw output. We will re-run it.

## Sources

- The measurement logs listed in [04-validation.md](04-validation.md#sources) (2026-08-15,
  2026-08-28, 2026-08-31) and [05-serving-models.md](05-serving-models.md)
- `perftest` (ib_write_bw) flag meanings: https://github.com/linux-rdma/perftest
- NVIDIA DGX Spark User Guide, ConnectX-7 Networking: https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html
