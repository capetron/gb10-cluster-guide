# data/

`gb10-cluster-bandwidth-2026.csv`: one row per bandwidth measurement in
[docs/10-benchmark-data.md](../docs/10-benchmark-data.md). Columns:

| Column | Meaning |
|---|---|
| `date` | the day the measurement was taken (ET), matching the log dates in docs/04 |
| `topology` | `direct cable`, `one switch` or `two switches` |
| `nodes` | number of GB10 workstations in the fabric during the run |
| `path` | what was measured: which pair, which PCIe half, which round of the six-node matrix |
| `tool` | `ib_write_bw` (RDMA, the authority) or `iperf3` (TCP sanity check) |
| `flags` | the command-line flags used; `<peer>` and `-d <hca>` vary per node |
| `result_gbps` | the reported wire rate in Gb/s; for concurrent runs the sum, with the parts in `notes` |
| `notes` | the component figures, counters and the condition behind any low number |

Rows marked "misconfiguration" are kept on purpose: they are what a broken path looks
like, and they are the fastest way to recognise one.

Licence: CC BY 4.0, same as the guide. Cite as described in docs/10-benchmark-data.md.
