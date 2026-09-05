# 04. Validation: proving the fabric runs at line rate

**Summary.** Before any model touches the fabric, measure it with RDMA tools, one PCIe
half at a time and then both, one pair at a time and then all pairs concurrently. This
document is the matrix we ran on six GB10 workstations across two switches: intra-switch
pairs, a single cross-switch flow over the 200G inter-switch link, two same-direction
flows sharing the ISL, and a bidirectional ISL load with all six nodes busy. The headline
results: 196 Gb/s per node through the switch ASIC with both halves active, 109 Gb/s
per half through the switch (against 111.86 Gb/s on a direct cable), no measurable ISL
penalty for a single cross-switch flow, a fair 82 + 82 Gb/s split when two 100G senders
share one ISL direction, and 327 Gb/s aggregate with three concurrent pairs including a
bidirectional ISL. It also explains why a single TCP stream is the wrong tool, how to
find the right GID index, why a background `ib_write_bw` server dies with your SSH
session, and what the `packet_seq_err` counter is telling you.

## The tools and why

- **`ib_write_bw`** (from the `perftest` package) drives RDMA writes between two hosts and
  reports the wire rate. It exercises the same path NCCL uses. It is the authority.
- **`iperf3`** measures TCP. On the GB10's ARM cores a single TCP stream sits near 12 Gb/s
  regardless of the link, so a single-stream iperf3 number tells you about the CPU, not
  the fabric. We report iperf3 only as a sanity check next to the RDMA figure.
- **`ping -M do -s 8972`** proves MTU 9000 end to end and is the fastest way to spot a
  detour through a 1500-byte path.
- **NIC counters** (`ethtool -S`, and the RDMA hardware counters under
  `/sys/class/infiniband/<hca>/ports/1/hw_counters/`) tell you whether loss is happening.

## Finding the RDMA device and GID index

Each QSFP port has two RDMA devices, one per PCIe half (`rocep1s0f0` and `roceP2p1s0f0`
for Port 0). RoCE v2 needs a GID index that maps to the IPv4 address on that half, and
**GID indices are not stable across nodes or ports**. Never hard-code one. Look it up:

```
hca=rocep1s0f0
for i in /sys/class/infiniband/$hca/ports/1/gids/*; do
  idx=${i##*/}
  echo "$idx $(cat $i) $(cat /sys/class/infiniband/$hca/ports/1/gid_attrs/types/$idx 2>/dev/null)"
done
```

Pick the entry whose type is RoCE v2 and whose GID ends in the IPv4 address you assigned
to that half (the last four bytes of an IPv4-mapped GID are the address). On our units it
was index 3 on every half, and the launchers in [05-serving-models.md](05-serving-models.md)
use `NCCL_IB_GID_INDEX=3`, but verify on yours.

## Running a measurement

Server side (on the receiving node). Run it detached, or it dies with your SSH session and
the client reports "Couldn't connect", which looks exactly like a firewall problem and is
not:

```
ssh gb10-02 'sh -c "nohup ib_write_bw -d rocep1s0f0 -x 3 -F -D 6 -s 65536 --report_gbits </dev/null >/tmp/ibw.log 2>&1 &"'
```

Client side:

```
ib_write_bw -d rocep1s0f0 -x 3 -F -D 6 -s 65536 --report_gbits 198.51.100.2
```

Flags: `-d` RDMA device, `-x` GID index, `-F` ignore CPU frequency warnings, `-D`
duration in seconds, `-s` message size in bytes, `--report_gbits` print Gb/s. The 65,536
byte, 6 second run is what our six-node matrix used. Our earlier direct-attach runs used
`-q 8 -s 1048576 -D 10` (eight queue pairs, 1 MiB messages, ten seconds); both give the
same wire rate on a healthy link.

For the both-halves number, run two client/server pairs at once, one on `rocep1s0f0`
against the half-A address and one on `roceP2p1s0f0` against the half-B address, and add
the two results.

For the concurrent matrix, start every server first, then launch every client in the
same second from a script, then collect. A helper that polls for a done marker in the
logs must delete the old logs first or it will read the previous run.

## Baselines: direct cable

Two units, one 0.5 m QSFP112 DAC, no switch:

| Test | Result |
|---|---|
| One half, `ib_write_bw` | 111.86 Gb/s |
| Both halves concurrently | 98.04 + 98.04 = 196.08 Gb/s (98 percent of line rate) |
| One half on a firmware power-throttled NIC (before OS and firmware update) | 12.74 Gb/s |

The throttled unit showed 200G, RS-FEC, PCIe Gen5 x4 and a clean `mstlink` while
delivering 12.74 Gb/s. Only this measurement revealed it. Re-run after any rebuild.

## Through one switch

Four MSI units on the first switch, measured between the two units on **different** DD
ports so the traffic crosses the switch ASIC rather than staying inside one breakout:

| Test | Result |
|---|---|
| Both halves, `ib_write_bw`, 65,536 B, 6 s | 98.0 + 98.0 = 196 Gb/s |
| iperf3 TCP on both halves | 93.1 + 92.6 Gb/s |

No PFC, no ECN. Two DGX Spark units on the second switch, one half:

| Test | Result |
|---|---|
| `ib_write_bw` through switch B | 109.11 Gb/s (direct-attach baseline 111.86) |
| Jumbo ping both planes | clean |

The switch costs about 0.75 Gb/s per half, 0.7 percent. That is the whole penalty.

## The six-node matrix (all six concurrent where stated)

All runs: `ib_write_bw`, 65,536 byte messages, `--report_gbits`, one half per pair. Pairs
are listed as client to server. A four-node tensor-parallel serving run was live on the
first switch's units throughout and survived every round.

| Round | Pairs | Result, Gb/s |
|---|---|---|
| R1, intra-switch, three pairs | gb10-01 to gb10-02; gb10-03 to gb10-04; gb10-05 to gb10-06 | 109.31 + 109.22 + 109.27 = **327.8 aggregate** |
| R2a, one cross-switch flow over the ISL | gb10-05 to gb10-01 | **109.08** (no measurable ISL penalty) |
| R2b, two cross-switch flows in the same direction, plus one intra | gb10-05 to gb10-01; gb10-06 to gb10-02; gb10-03 to gb10-04 | **81.92 + 81.90** (163.8 on the 200G ISL, fair split) + 109.13 intra |
| R3, bidirectional ISL, plus one intra | gb10-05 to gb10-01; gb10-02 to gb10-06; gb10-03 to gb10-04 | 109.19 + 109.10 + 109.14 = **327.4 aggregate** |

Reading the rows:

- **R1** says the two pods are indistinguishable. A DGX Spark pair and an MSI pair land
  within 0.1 Gb/s of each other.
- **R2a** says the ISL costs nothing for one flow. 109.08 through two switches and a
  200G DAC versus 109.31 through one switch.
- **R2b** is the only oversubscribed case: two 100G senders into one 200G ISL direction
  is 200 into 200 with no headroom, and each half only ever delivers about 109. The ISL
  split them almost perfectly evenly at 81.9 each, 163.8 total, with no PFC configured.
  DCQCN (the RoCE congestion control in the NIC, driven by ECN marks and congestion
  notification packets) handled it. This is also the only round where `packet_seq_err`
  grew, by about 5,500 over the run.
- **R3** says the ISL is full duplex. One flow in each direction plus an intra-switch pair
  gives the same 327 Gb/s aggregate as three intra-switch pairs.

Before the RSTP fix in [03-switched-fabric.md](03-switched-fabric.md), the R2a path
measured 4.47 Gb/s. We first attributed it to contention (the four MSI units were loading
a model at the time), and the idle re-test above shows the real path. If you see a
cross-switch number in the single digits, check the ISL's RSTP role before checking
anything else.

## What `packet_seq_err` means

`packet_seq_err` is a ConnectX hardware counter (under the RDMA device's `hw_counters`)
that increments when the NIC receives a RoCE packet whose packet sequence number is not
the one it expected. On a lossless-by-assumption RDMA transport that means a packet was
lost or reordered in flight and the responder is asking for a retransmit. Two very
different situations produce it:

1. **Oversubscription with congestion control working.** R2b above: two 100G senders
   into one 200G direction. The switch marks or drops under pressure, the NICs send
   congestion notification packets, DCQCN backs the senders off, and the counter grows
   by a few thousand while throughput settles at a fair split. Throughput is fine. The
   counter is telling you the ISL is at capacity, which you already knew.
2. **A path that is dropping most of what it is given.** The second-bridge trap in
   [03-switched-fabric.md](03-switched-fabric.md): the switch CPU could forward a few
   Gb/s and dropped the rest. The counter grew, CNPs flew, and throughput collapsed
   from 196 to under 5 Gb/s. The counter is telling you the path is broken.

Tell them apart by throughput: if `ib_write_bw` reports near line rate, the errors are
congestion feedback and DCQCN is doing its job; if it reports single digits with the
same counter growing, something in the path is software-forwarding, mis-negotiated, or
running at MTU 1500. Under no circumstances does a healthy, unloaded pair grow this
counter; R1, R2a and R3 grew it by zero.

If you run many cross-switch senders routinely, PFC and ECN on the ISL are the next
knobs. We have not needed them.

## Confirming the model is actually using the fabric

After a serving run, read the byte counters on the RDMA device and compare to before.
During a four-node GLM-5.3-Flash run, 17 GB crossed `rocep1s0f0` on the head node;
during a two-node Qwen3.8-Flash-Next run, 11 GB. If the counter did not move, NCCL fell
back to sockets over the management network and every result you collected is a
management-LAN result (see the 539 versus 1,963 tok/s comparison in
[02-two-and-three-nodes.md](02-two-and-three-nodes.md)).

## Sources

- Our measurement logs: 2026-08-15 (direct-attach 111.86 and 196.08 Gb/s, 12.74 Gb/s throttle, `-q 8 -s 1048576 -D 10` flags, GID index lookup path, single-stream TCP near 12 Gb/s), 2026-08-28 (196 Gb/s through the switch ASIC, iperf3 93.1 + 92.6, 65,536 B / 6 s flags, 17 GB and 11 GB RDMA byte counts), 2026-08-31 (109.11 DGX Spark pair, six-node matrix R1 to R3, packet_seq_err growth of about 5,500 in R2b, 4.47 Gb/s before the RSTP fix, second-bridge collapse to 4.85 / 4.9 / 8.8 Gb/s, detached `ib_write_bw` server gotcha)
- `perftest` (ib_write_bw) documentation for flag meanings: https://github.com/linux-rdma/perftest
- NVIDIA DGX Spark User Guide, ConnectX-7 Networking (RDMA device names): https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html
