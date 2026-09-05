# Clustering NVIDIA GB10 workstations

**Two nodes, a three-node ring, and a switched 200G RoCE fabric for four or more.**

By Petronella Technology Group, Inc. (Raleigh, North Carolina). License: CC BY 4.0.

This guide documents what we built and measured while clustering six NVIDIA GB10 Grace
Blackwell workstations: four MSI EdgeXpert MS-C931 units and two NVIDIA DGX Spark
Founders Edition units, joined by two MikroTik CRS812-8DS-2DQ-2DDQ-RM switches with a
200G inter-switch link, running vLLM tensor-parallel and expert-parallel serving across
the fabric. As far as we know it is the only public write-up of a switched multi-node GB10
fabric with measured RDMA and token-throughput numbers. Every number here comes from our
own logs or from NVIDIA and vendor documentation, and each document ends with its sources.

We sell the 0.5 m QSFP112 400G direct-attach cable that every GB10 workstation needs for
clustering. That is why this guide exists. We have tried to keep the product links to the
places where a reader would want them (the bill of materials, the decision tree, and the
spots where the text says "the cable") and nowhere else.

## Who this is for

- Anyone with two or three GB10 workstations who wants them to work as one memory pool.
- Anyone with four or more who needs to pick a switch, configure it correctly on the first
  try, and prove the fabric is running at line rate before blaming the model.
- Anyone deciding whether to buy a fourth, sixth, or eighth unit, and what that buys.

## Decision tree

```
How many GB10 workstations?

  1  ->  No cable needed. Read docs/05-serving-models.md for what a single unit does
         (a 128 GB unified pool, roughly 200B-parameter models, memory-bandwidth bound).

  2  ->  One cable, port to port. NVIDIA's "Connect Two Sparks" playbook.
         Full 200 Gb/s needs traffic on both PCIe halves of the port (NCCL does this).
         Read docs/02-two-and-three-nodes.md.
         Cable: https://petronellatech.com/hardware/dgx-spark-cluster-cable/

  3  ->  Three cables in a ring, each unit uses both QSFP ports. NVIDIA-official,
         switchless. This is the switchless ceiling: each unit has only two ports.
         Read docs/02-two-and-three-nodes.md.
         Ring kit (3-pack): https://petronellatech.com/blog/dgx-spark-cluster-cables-in-stock-0-5m-qsfp112-400g-dac-for-every-gb10-workstation-159-shipped/

  4+ ->  A 200G-capable switch. We used MikroTik CRS812-8DS-2DQ-2DDQ-RM with
         QSFP56-DD to 2x QSFP56 breakout DACs and the same 0.5 m QSFP112 cable
         from each node to the breakout. One node cable per unit.
         Read docs/03-switched-fabric.md, then docs/04-validation.md.
         NVIDIA's documented switch playbook covers up to four systems; six on
         two switches (what we run) is outside that envelope and is described
         here as measured, not as supported.

  6  ->  One model will not span six with the checkpoints we tried (tensor
         parallel needs a divisor of the head and expert counts). Run pools
         of pairs or a four-node group plus a pair. Eight divides cleaner.
         Read docs/05-serving-models.md, "Six nodes".
```

## Table of contents

| Document | What it covers |
|---|---|
| [docs/01-hardware.md](docs/01-hardware.md) | The GB10 variants, what the ConnectX-7 port really is (two PCIe Gen 5 x4 halves), why the cable is 400G-rated while the link is 200G, and the 273 GB/s memory bus the link is competing with |
| [docs/02-two-and-three-nodes.md](docs/02-two-and-three-nodes.md) | One cable, the three-cable ring, addressing, MTU 9000, link checks, and what a bond does not give you |
| [docs/03-switched-fabric.md](docs/03-switched-fabric.md) | The CRS812 build: forcing the DD breakout to 200G-baseCR4, jumbo frames, the inter-switch link, the RSTP trap with dual uplinks, the second-bridge trap that dropped 196 Gb/s to 5 Gb/s, and what we settled on |
| [docs/04-validation.md](docs/04-validation.md) | The ib_write_bw and iperf3 matrix (intra-pod, cross-pod, bidirectional ISL) with the measured numbers, how to reproduce them, and what packet_seq_err means |
| [docs/05-serving-models.md](docs/05-serving-models.md) | vLLM on sm_121: why the stock image fails, the community patch chain, four-node GLM-5.3-Flash and Qwen3.8-Flash-Next results, the H200 reference, six-node findings, NCCL over RoCE settings |
| [docs/06-bill-of-materials.md](docs/06-bill-of-materials.md) | Cables, switch, breakout and ISL DACs, what to budget |
| [docs/07-faq.md](docs/07-faq.md) | Short answers to the questions we get asked |
| [docs/SANITIZATION-NOTES.md](docs/SANITIZATION-NOTES.md) | What was generalized from our production notes to make this public |

## The numbers in one screen

All measured on our fabric; details and methodology in [docs/04-validation.md](docs/04-validation.md)
and [docs/05-serving-models.md](docs/05-serving-models.md).

| Measurement | Result |
|---|---|
| Direct cable, one PCIe half, ib_write_bw | 111.86 Gb/s |
| Direct cable, both halves concurrently | 98.04 + 98.04 = 196.08 Gb/s |
| Through the switch, both halves, crossing the switch ASIC | 98.0 + 98.0 = 196 Gb/s |
| DGX Spark pair through the switch, one half | 109.11 Gb/s |
| Cross-switch over the 200G ISL, one flow | 109.08 Gb/s (no measurable ISL penalty) |
| Two same-direction 100G flows into the 200G ISL | 81.92 + 81.90 = 163.8 Gb/s (fair split) |
| Six nodes, three concurrent pairs, ISL bidirectional | 109.19 + 109.10 + 109.14 = 327.4 Gb/s aggregate |
| Second bridge on the switch (the trap) | 196 to 4.85 Gb/s |
| GLM-5.3-Flash NVFP4, TP4, decode (prose / code / math) | 26.5 / 38.1 / 46.7 tok/s |
| GLM-5.3-Flash NVFP4, TP4, prefill (warm) | 3,840 tok/s, TTFT 2.3 s at 8.9k tokens |
| GLM-5.3-Flash NVFP4, TP4, KV cache | 2,246,948 tokens (16 GiB fp8 per rank) |
| Qwen3.8-Flash-Next NVFP4, TP4 + expert parallel, decode | 39.6 / 57.0 / 76.9 tok/s |
| Qwen3.8-Flash-Next NVFP4, TP4 + expert parallel, six streams | 167.4 tok/s aggregate |
| Six nodes as three TP2 pairs, pool aggregate | ~386 tok/s decode, ~9,450 tok/s prefill |

## Where the product links live

- Cable hub: https://petronellatech.com/hardware/dgx-spark-cluster-cable/
- Ring kit and bundles: https://petronellatech.com/blog/dgx-spark-cluster-cables-in-stock-0-5m-qsfp112-400g-dac-for-every-gb10-workstation-159-shipped/
- Why 400G on the label and 200G on the link: https://petronellatech.com/blog/dgx-spark-cluster-bandwidth-what-400g-really-means/
- Our self-hosted LLM benchmarks, including the four-GB10 rows: https://petronellatech.com/ai/llm-benchmarks/

Prices at publication: single cable $159, 2-pack $299, 3-pack ring kit $435, free shipping
inside the United States, United States addresses only.

## About us

Petronella Technology Group, Inc. is a cybersecurity and compliance firm in Raleigh, North
Carolina. We build and operate private AI infrastructure for clients who cannot send their
data to a public model, and we run the same hardware ourselves. Craig Petronella (CMMC-RP,
CCNA) leads the firm. Phone: 919-348-4912.

## Contributing and corrections

If a number here disagrees with what you measure, open an issue with your command line and
the raw output. We will re-run it. We do not accept numbers without a command line.

## License

CC BY 4.0. See [LICENSE](LICENSE). Attribution: "Petronella Technology Group, Inc.,
Clustering NVIDIA GB10 workstations, https://petronellatech.com".
