# 05. Serving models across the fabric: vLLM on sm_121

**Summary.** The GB10's GPU is CUDA compute capability 12.1 (`sm_121`), and as of
August 2026 the vendor vLLM images for the two models we care about did not run on it
without patches. This document describes, generically, why the stock image fails and
what the community patch chain fixes; credits the public recipes we built on; and then
gives the measured numbers for the configurations that worked: GLM-5.3-Flash NVFP4 with
tensor parallel 4 across four nodes (26.5 / 38.1 / 46.7 tok/s decode by workload, 3,840
tok/s warm prefill, a 2.25M-token KV cache), Qwen3.8-Flash-Next NVFP4 with tensor
parallel 4 plus expert parallel (39.6 / 57.0 / 76.9 tok/s, 167 tok/s across six streams,
2.64M-token KV), the two-node and single-node variants, the four-H200 reference, what
happens when you try to span six nodes, and the NCCL-over-RoCE environment that makes
any of it work. Every number is from our own runs at temperature 0 with the methodology
in the last section.

## Why the stock image fails on sm_121

We tried the day-zero vendor image for GLM-5.3-Flash on four GB10 units and it died five
different ways before producing a token. Each failure is a real bug class you will meet
on any new model on this GPU, so they are worth knowing by name:

1. **No usable attention backend for the model's KV layout.** GLM-5.3-Flash uses a
   NoPE multi-head latent attention (rotary dimension zero). The only sparse-MLA backend
   the image enabled for capability 12 hard-required a DeepSeek-style rotary dimension
   of 64 and died in warmup. The Hopper NoPE backend supports the layout but was gated to
   capability 9. Fix: extend that backend's capability gate to include 12, and select its
   FlashAttention-2 path (the FA3 path is Hopper-only).
2. **A NaN in the attention kernel at specific batch sizes.** The image's FlashInfer
   release produced NaN for 64 to 256-row batches on sm_121 (1 to 6 rows and 512 plus
   were clean). A later FlashInfer nightly fixed it; the fix is to install that nightly
   and remove the ahead-of-time kernel cache so nothing stale loads.
3. **A silent NCCL downgrade.** Installing the FlashInfer nightly pulled NCCL from 2.30.7
   down to 2.29.7, and 2.29.7 fails `ncclCommInitRank` with an internal error on the
   RoCE fabric. Fix: re-pin NCCL 2.30.7 in the same layer. (The same downgrade happens
   when installing some model-loader packages. Pin it every time.)
4. **A CUTLASS DSL version mismatch** introduced by the same nightly that broke the
   CuTeDSL warmup. Fix: re-pin the version the base image was qualified with.
5. **A Programmatic Dependent Launch race.** PDL is enabled for any capability at or
   above 9, including 12, in the Triton kernels that carry the model's recurrent state.
   On GB10 that produced a timing-dependent read-before-store race: some boots NaN,
   some did not, and debug hooks that add device syncs masked it. Fix: gate PDL to
   capabilities 9 and 10 only.

Two more patches on top of those: initialize the sparse-attention indexer's top-k
destination to a sentinel instead of uninitialized memory (uninitialized pool ids
produced a second NaN class), and cap the fp8 KV cache tile size for the FA2 MLA path
so it fits the GB10's roughly 101 KB of opt-in shared memory instead of assuming
Hopper's 228 KB.

The lesson that generalizes: **on a new GPU, assume the image's attention backend
selection, kernel library version, and NCCL version are all wrong until a multi-node
run has produced a coherent answer.** The failures above look like network faults
(NCCL init errors), model bugs (NaN), or hardware faults (silent worker death), and
none of them were.

## The community recipes we built on

All of the above came from public repositories, and we are grateful to their authors.
We copied their patch stacks, built the images locally, and did not change the patches.

- **tonyd2wild/GLM-5.3-Flash-NVFP4-1M-KV-4x-DGX-Spark** (GitHub): the sm_121 patch chain
  for GLM-5.3-Flash (the seven Dockerfiles that fix items 1 through 5 plus the indexer
  and fp8 tile patches), a DFlash2 speculative-decoding overlay, the cache-flusher
  sidecar, and the chat template. Our four-node GLM numbers below match this recipe's
  published four-Spark figures (35.7 tok/s median, 55 to 64 on structured output).
- **tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark** (GitHub): the two-node
  variant, including the memory settings that make a two-node boot survive.
- **x00byte/Qwen3.8-Flash-Dual-Spark-Recipe** (GitHub): the two-node Qwen3.8-Flash-Next
  recipe and a prebuilt image with a patched PLE layer for the hybrid NVFP4 plus FP8
  checkpoint. The image is published on Docker Hub by the recipe author; see the repo.
- **blazux/qwen3.8-Flash-DGX** (GitHub): the single-node variant that memory-maps the
  model's 47.7 GiB n-gram table from NVMe instead of holding it resident.
- **MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks** (GitHub): an SGLang two-node lane we
  measured for comparison (it tied on code and lost on prose, math, aggregate and
  prefill to the vLLM lane; we kept vLLM).

Checkpoints: `RedHatAI/GLM-5.3-Flash-NVFP4` (compressed-tensors, 198 GB) and
`RadixArk/Qwen3.8-Flash-Next-NVFP4` (135 GB), both on Hugging Face.

## Results: GLM-5.3-Flash NVFP4

### Four nodes, tensor parallel 4 (the configuration the recipe is written for)

Flags that matter: `--tensor-parallel-size 4 --nnodes 4`, `--enforce-eager`,
`--moe-backend marlin`, `--kv-cache-dtype fp8_e4m3`, `--block-size 2304`, MTP
speculative decoding with 4 draft tokens, one RDMA device per node, 16 GiB of KV per
rank, `--max-model-len 262144`.

Boot: 46.8 GiB of weights per rank loaded in 347 s; GPU KV cache **2,246,948 tokens**
(16 GiB fp8 per rank); API up at 600 s. 17 GB crossed the RDMA device during the run.
Zero NaN.

| Metric | Result |
|---|---|
| Decode, prose / code / math (single stream, 256 tokens) | 26.5 / 38.1 / 46.7 tok/s |
| Prefill, cold (first 8.9k-token prompt) | 725 tok/s, TTFT 12.3 s |
| Prefill, warm | **3,840 tok/s, TTFT 2.3 s** |
| Six concurrent streams, aggregate decode | 91.2 tok/s (about 15 per stream) |
| Four concurrent streams, cold | 36 tok/s aggregate |

Variants we measured against it:

- **Both RDMA devices per node** (`NCCL_IB_HCA=rocep1s0f0,roceP2p1s0f0`, 196 versus
  98 Gb/s): prefill +9 percent (4,186 tok/s), decode -5 to -9 percent, six-stream
  aggregate -11 percent. GLM's tensor-parallel all-reduce is latency-bound, not
  bandwidth-bound; keep one device.
- **DFlash2 speculative decoding, K=7** (drafter `incoai/GLM-5.3-Flash-DFlash2`):
  27.5 / 40.5 / **69.2** tok/s single stream (math +48 percent), prefill 4,065, but
  six-stream aggregate **48.5** (-47 percent). Mean acceptance length 3.09 alone and
  1.97 under six streams; long drafts are mostly wasted once batched. Use it for a
  single-user coding or math endpoint, not a shared one. The recipe's 21.8 to 46.9
  tok/s claim is for structured single-stream output and does not carry to prose or
  concurrency.

### Two nodes, tensor parallel 2

Five attempts failed at memory: weights load at 92.76 GiB per rank in 260 s, and on the
GB10's unified pool the committed memory tracks weights plus runtime, not the
`--gpu-memory-utilization` cap. With 121.7 GiB visible, 92.8 GiB of weights and about
5 GiB of host, roughly 24 GiB remained for CUDA context, NCCL, the MoE workspace, the
MTP draft and the KV cache, and the runtime needed more. A container memory cgroup never
engaged because GPU and unified-memory allocations are not cgroup-charged.

The sixth attempt, following the two-node recipe exactly, booted: no container memory
cap, `--kv-cache-memory 4445787956` (the 4.14 GiB vLLM itself suggested, the only value
the recipe author's six-boot ladder survived), and no memory guard above a 2 percent
wedge backstop. Boot 468 s for weights, KV **507,041 tokens**, API at 750 s, host
MemAvailable floor 3 to 4 percent.

| Metric | TP2, MTP-4 | TP2, DFlash2 K=7 |
|---|---|---|
| Decode prose / code / math | 16.0 / 21.4 / 31.1 | 16.6 / 23.4 / 49.8 |
| Prefill warm | 1,495 tok/s, TTFT 5.95 s | 1,479 tok/s, TTFT 6.0 s |
| Six-stream aggregate | 52.1 | 49.4 |
| KV cache | 507,041 tokens | 457,414 tokens |

Against four nodes: decode at 56 to 67 percent, prefill at 39 percent, aggregate at
57 percent, KV at 23 percent. Two nodes is a "free the other pair for something else"
configuration, not a faster one, and it runs at a 3 to 4 percent host-memory floor that
we would not leave unattended on boxes with no remote power control.

## Results: Qwen3.8-Flash-Next NVFP4

### Two nodes, tensor parallel 2

Weights 64.8 GiB per rank in 563 s; KV **1,850,932 tokens** (32.6 GiB per rank); API at
about 11 minutes; 11 GB over the RDMA device; zero NaN. Thinking is on by default in this
model's chat template: a small `max_tokens` returns `content: null`, so pass
`chat_template_kwargs: {"enable_thinking": false}` or budget at least about 150 tokens.

| Metric | Result |
|---|---|
| Decode prose / code / math | 35.3 / 36.0 / 53.2 tok/s |
| Prefill warm | 2,303 tok/s, TTFT 3.9 s |
| Six-stream aggregate | 118.1 tok/s (about 20 per stream) |

### Four nodes: plain tensor parallel 4 cannot load

Every rank raised `NotImplementedError: Intermediate size padding for w1 and w3 ...
FLASHINFER_CUTLASS`. The model's `moe_intermediate_size` is 640 across 512 experts;
TP2 slices it to 320, which is fine, and TP4 slices it to 160, which is below the NVFP4
MoE kernel's alignment and padding is unsupported. It is not memory (57 percent was
free when it died).

The fix is `--enable-expert-parallel`: each rank holds 128 whole experts instead of a
slice of every expert. (A different NVFP4 MoE checkpoint, Gemma-4-26B-A4B, could not
tensor-shard at all for the same reason at TP2 or TP4; expect this class of error on
small-intermediate MoE checkpoints.)

### Four nodes, tensor parallel 4 plus expert parallel (the winner)

Configuration: TP4 + EP, eager execution, MTP-4, both RDMA devices per node,
`--gpu-memory-utilization 0.65`, prefix caching on, `--max-num-seqs 32`.

Boot: 33.7 GiB of weights per rank in 313 s; API at about 12 minutes; KV
**2,643,285 tokens** (40.4 GiB per rank); MemAvailable 18 to 22 percent on all nodes at
rest.

| Metric | Result |
|---|---|
| Decode prose / code / math | **39.6 / 57.0 / 76.9 tok/s** |
| Prefill warm | 3,547 tok/s, TTFT 2.51 s |
| Six-stream aggregate | **167.4 tok/s** (cold pass 178.0) |

Against two nodes: +21 to +54 percent decode, +46 percent prefill, +40 percent
aggregate. The public benchmark page carries this row as 40 to 77 tok/s single stream and
167 to 184 tok/s across six streams with a 2.6M-token KV cache:
https://petronellatech.com/ai/llm-benchmarks/ .

Variants that lost:

- **Piecewise CUDA graphs** instead of eager (same utilization): 25.5 / 37.1 / 44.6,
  aggregate 115.9, and the profiler left only 415,766 KV tokens. Keep eager.
- **MTP-6** instead of MTP-4: 34.8 / 55.0 / 70.2, prefill 2,457, aggregate 161.5; mean
  acceptance 3.64 of 6 drafts, wasted verification. Keep MTP-4.
- **One RDMA device** instead of two: 42.6 / 55.5 / 67.0, prefill 3,363, aggregate 164.8.
  Dual devices won on math (+15 percent) and prefill (+5 percent); expert-parallel
  all-to-all benefits from the 196 Gb/s. Prose -7 percent is inside the noise band.
- **Utilization 0.72**: the head node (which also runs the API server and a desktop
  session) dropped to 11 percent MemAvailable during an 8.9k-token prefill and the
  memory guard removed the container. 0.65 is the four-node number.

### One node, n-gram table memory-mapped

The single-node recipe memory-maps the model's 47.7 GiB n-gram table from NVMe instead of
holding it resident. Weights 79.31 GiB resident in 647 s (mmap prewarm 47.7 GiB in
29 s); KV 8.8 GiB = **296,636 tokens**; API at about 13 minutes.

| Metric | Result |
|---|---|
| Decode prose / code / math | 24.8 / 31.1 / 33.8 tok/s |
| Prefill warm | 2,376 tok/s, TTFT 3.7 s |
| Six-stream aggregate | 86.4 tok/s (14.4 per stream) |

One unit alone does about 70 percent of a TP2 pair per stream and 73 percent of its
aggregate, at a 297K-token KV instead of 1.85M. Four independent single-node endpoints
would give about 345 tok/s aggregate against 167 for TP4 + EP, trading per-stream speed
and context for aggregate. The memory-mapped table costs nothing measurable once the
page cache is warm.

The first attempt at this configuration died silently seven seconds after the KV cache
was allocated, with no traceback. It was not vLLM: the head node ran `earlyoom`, whose
default 10 percent MemAvailable floor sent SIGTERM to the vLLM worker. Diagnose with
`journalctl -u earlyoom`, not `dmesg`. See the memory section below.

## Six nodes: one model cannot span six (with these checkpoints)

With two DGX Spark units on the second switch we tried to run Qwen3.8-Flash-Next across
all six. Three findings, each definitive for this checkpoint and image:

1. **File descriptor limit.** Six-rank NCCL exceeds Docker's default `nofile=1024`
   ("Too many open files" in the socket reset path). Four ranks fit under it by luck.
   Set `--ulimit nofile=1048576:1048576` on every multi-node container.
2. **TP6 is impossible.** `AssertionError: 16 is not divisible by 6` in the NVFP4 MoE
   kernels, even with expert parallel (which got further than we expected; 512 experts
   over 6 was not the tripwire).
3. **Pipeline parallel is impossible.** TP2 x PP3 dies loading weights:
   `ValueError: no module or parameter named 'hyper_connection_mixer'`. The
   architecture's cross-layer hyper-connections are not sliceable by pipeline stage in
   this vLLM implementation. Architectural, not configuration.

So six GB10 units serve this model as **pools**. We deployed three TP2 + EP pairs, each
pair within one switch (no ISL traffic), eager, MTP-4, both RDMA devices, utilization
0.65, `--max-num-seqs 32`, and benchmarked all three concurrently (warm pass):

| Pair | Decode prose / code / math | Prefill | Six-stream aggregate |
|---|---|---|---|
| gb10-01 + gb10-02 (MSI) | 32.5 / 43.7 / 47.1 | 3,170 | 128.6 |
| gb10-03 + gb10-04 (MSI) | 34.7 / 45.7 / 52.1 | 3,137 | 129.7 |
| gb10-05 + gb10-06 (DGX Spark FE) | 33.1 / 43.8 / 48.4 | 3,149 | 128.3 |

**Pool totals: about 386 tok/s decode aggregate across 18 streams and about 9,450 tok/s
of prefill capacity.** The DGX Spark pair is indistinguishable from the MSI pairs. Against
the four-node TP4 + EP endpoint (38.5 / 50 / 67.5 single stream, 3,550 prefill, 156 to 184
aggregate, 2.6M KV in that session's re-measure): the pool is 2.2x the aggregate and
uses all six units; TP4 is +15 to 30 percent per stream with the giant KV cache.

Why eight would divide cleaner than six: this model's 24 attention heads, 512 experts
and 640 MoE intermediate dimension all divide by 8 and none divide by 6. The fabric is
already provisioned for eight nodes on breakouts.

## The H200 reference

For scale, the same model family on datacenter parts, measured on the same harness and
published on the same benchmark page:

- GLM-5.3-Flash FP8 on four H200 with NVLink (575 GB): 233 to 339 tok/s single-stream
  decode against 26.5 to 46.7 on four GB10; coding score 0.987; 14,071 tok/s aggregate.
- A single H200: 202 tok/s single user, 7,777 tok/s aggregate.

Four GB10 units are roughly one tenth of four H200 on per-stream decode for this model,
at a fraction of the price and power, with a 2.25M-token KV cache. The comparison is on
the benchmark page with per-rep ranges, latency and dates:
https://petronellatech.com/ai/llm-benchmarks/ .

## Memory on a unified-memory GPU (read before an unattended run)

The GB10 exposes about 121 GiB to CUDA out of 128 GB, and the host shares it. Three
rules from our logs, all learned the hard way on machines with no remote power control:

- `--gpu-memory-utilization 0.85` leaves 1 to 4 percent MemAvailable on a GB10. It runs
  for hours and it is one allocation from a kernel OOM that may kill sshd or the network
  manager instead of the worker. Each 0.01 of utilization is about 1.2 GiB. Our rules:
  TP4 + EP at 0.65; a standing single-node endpoint at 0.72 to 0.75 with
  `--kv-cache-dtype fp8_e4m3` (same tokens in half the bytes); never 0.85.
- Run a memory guard on every rank: a loop that polls MemAvailable every 5 s and
  `docker rm -f`s the container below a floor (we use 12 percent). It fired once, on the
  head node during a long prefill, and the host stayed up. The container's own
  `--memory` cgroup will not save you because GPU and unified-memory allocations are
  not cgroup-charged.
- Know whether `earlyoom` is installed. On a unit that has it, the 10 percent default
  floor kills the vLLM worker with no traceback and `docker inspect` shows
  `OOMKilled=false`.

A root-owned sidecar that drops the page cache whenever `Cached` exceeds 40 GiB during
model load (the recipe's `cache_flusher.sh`, per an NVIDIA knowledge-base remedy)
helps the driver allocate the KV slab on a unit that has been serving files.

## NCCL over RoCE: the environment that works

From our launchers. Substitute your plane-A subnet and your GID index.

```
# Container
docker run ... \
  --ulimit memlock=-1:-1 --ulimit nofile=1048576:1048576 --cap-add IPC_LOCK \
  --device /dev/infiniband:/dev/infiniband \
  -e NCCL_NET=IB -e NCCL_IB_DISABLE=0 \
  -e NCCL_IB_HCA=rocep1s0f0,roceP2p1s0f0 \      # one device for GLM TP4; both for Qwen TP4+EP
  -e NCCL_IB_GID_INDEX=3 \                        # look it up, see 04-validation.md
  -e NCCL_IB_ROCE_VERSION_NUM=2 -e NCCL_IB_ADDR_FAMILY=AF_INET \
  -e NCCL_IB_ADDR_RANGE=198.51.100.0/24 \
  -e NCCL_SOCKET_IFNAME=enp1s0f0np0 -e GLOO_SOCKET_IFNAME=enp1s0f0np0 -e TP_SOCKET_IFNAME=enp1s0f0np0 \
  -e NCCL_NVLS_ENABLE=0 -e NCCL_CROSS_NIC=0 -e NCCL_IB_MERGE_NICS=0 -e NCCL_CUMEM_ENABLE=0 \
  -e NCCL_IGNORE_CPU_AFFINITY=1 \
  -e NCCL_DEBUG=WARN -e TORCH_NCCL_ASYNC_ERROR_HANDLING=1 \
  -v $HOME/.cache/huggingface:/hf \             # mount the WHOLE cache, see below
  <image> vllm serve /hf/hub/models--.../snapshots/<hash> \
    --tensor-parallel-size 4 --pipeline-parallel-size 1 --nnodes 4 \
    --master-addr 198.51.100.1 --master-port 29500 --node-rank <r> \
    --distributed-executor-backend mp \
    --speculative-config '{"method":"mtp","num_speculative_tokens":4}' \
    --max-model-len 262144 --max-num-seqs 32 --enable-chunked-prefill \
    --gpu-memory-utilization 0.65 --kv-cache-dtype fp8_e4m3 --enforce-eager \
    --enable-expert-parallel \                   # Qwen3.8-Flash-Next only
    --host 0.0.0.0 --port 8000
```

Start the worker ranks first (highest rank to lowest), then the head. Use vLLM's native
`--nnodes / --node-rank / --distributed-executor-backend mp`; Ray is not in the aarch64
images. Set `NCCL_NET=IB` explicitly: with `NCCL_IB_DISABLE=1` alone NCCL still probes
ibverbs, and with it unset on a unit whose RoCE devices are misconfigured NCCL can fall
back to sockets over the management LAN silently (check the RDMA byte counters, see
[04-validation.md](04-validation.md)).

Traps around the launch, each of which cost us one:

- **Hugging Face snapshot directories are relative symlinks into `../../blobs`.**
  Bind-mounting only the snapshot gives the container dangling links ("no config.json",
  "Invalid repository ID"). Mount the whole cache and address the snapshot beneath it.
- **Pin the image digest across nodes.** Two nodes on the same nightly tag from
  different days gave a bootstrap "Message truncated: received 176 bytes instead of
  172", which is an NCCL version mismatch, not a network fault.
- **Host firewalls need the full peer mesh including the node itself.** The collective
  bootstrap opens dynamic ports and the head connects to its own address.
- **Weight distribution.** Fan weights out over the fabric with `tar | ssh` (about 830
  MB/s, roughly four minutes per node for 185 GB) and images with
  `docker save | zstd | ssh docker load`. Do not pull 20 GB images on every node
  through a slow uplink.
- **First-load-after-boot defect on one image.** One two-node NVFP4 configuration
  loaded only once per boot; every restart failed in the MoE weight prep with
  `CUDA error: operation not permitted` on the worker and a gloo "connection closed by
  peer" on the head. Recovery was a reboot of both nodes. We report it so you do not
  spend a day on it; we did not root-cause it.

## Methodology

All serving numbers come from one script run on the head node against the
OpenAI-compatible endpoint: temperature 0; single-stream decode of 256 tokens on three
prompts (a short story for prose, a Python module with tests for code, a step-by-step
algebra problem for math) with `ignore_eos`; a roughly 8,900-token prompt with one
output token for prefill and TTFT; then N concurrent streams for aggregate. Every
configuration was run twice and the warm (second) pass is reported unless marked cold,
because vLLM enables prefix caching by default and the first pass pays for it. A
correctness probe (17 x 23 = 391) and a NaN scan of the outputs ran with every pass;
every configuration reported here passed both.

Numbers on the public page are from the same harness with per-rep ranges:
https://petronellatech.com/ai/llm-benchmarks/ and the generated leaderboards at
https://petronellatech.com/ai/llm-benchmarks/leaderboards/ .

## Sources

- tonyd2wild/GLM-5.3-Flash-NVFP4-1M-KV-4x-DGX-Spark, tonyd2wild/GLM-5.3-Flash-NVFP4-DFlash2-2x-DGX-Spark, x00byte/Qwen3.8-Flash-Dual-Spark-Recipe, blazux/qwen3.8-Flash-DGX, MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks (all on GitHub)
- Checkpoints: https://huggingface.co/RedHatAI/GLM-5.3-Flash-NVFP4 , https://huggingface.co/RadixArk/Qwen3.8-Flash-Next-NVFP4 , drafter https://huggingface.co/incoai/GLM-5.3-Flash-DFlash2
- Petronella Technology Group, Inc., self-hosted LLM benchmarks: https://petronellatech.com/ai/llm-benchmarks/ (four-GB10 row, single-H200 and four-H200 reference rows)
- Our optimization log, 2026-08-28 to 2026-08-31 (every configuration and number above; GLM TP4, TP2, DFlash2; Qwen TP2, TP4 + EP and its variants, single-node mmap; six-node findings and pool bench; earlyoom and memory floors), and the 2026-08-15 notes (digest drift, firewall mesh, first-load defect, Gemma-4 NVFP4 sharding error, 539 versus 1,963 tok/s over the LAN)
- Patch chain Dockerfile comments (failure classes 1 to 5, indexer and fp8 tile patches), copied from the tonyd2wild repository
