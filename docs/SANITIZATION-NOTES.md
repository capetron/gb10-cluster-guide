# Sanitization notes

This guide was written from Petronella Technology Group, Inc. internal build notes,
session handoffs and benchmark logs. Before publication the following classes of
detail were generalized. This file lists what was changed and how, so a reader knows
which identifiers are placeholders; it deliberately does not contain any of the
original values.

## Addressing

- All management-network addresses were replaced with the RFC 5737 documentation range
  192.0.2.0/24 (switches at 192.0.2.11 and 192.0.2.12).
- The RDMA fabric's two planes (one per PCIe half of the ConnectX-7 port) were replaced
  with 198.51.100.0/24 (plane A, half `enp1s0f0np0`) and 203.0.113.0/24 (plane B, half
  `enP2p1s0f0np0`). Host numbers follow the node number.
- The point-to-point /30 links from the earlier direct-attach ring were re-expressed in
  the same two documentation ranges.
- Overlay-network (mesh VPN) addresses that appeared in the source notes were removed;
  they play no part in the fabric.

## Hostnames

- The four MSI EdgeXpert MS-C931 units became `gb10-01` through `gb10-04`.
- The two NVIDIA DGX Spark Founders Edition units became `gb10-05` and `gb10-06`.
- The two switches became `crs812-a` (MSI pod) and `crs812-b` (DGX Spark pod).
- Every other host on our network that appeared in the source notes (workstations, other
  GPU servers, storage, management VMs, the campus core switches) was removed or
  replaced with a role description such as "the campus network" or "the management
  switch". Their names, addresses, ports and VLANs are not needed to reproduce the
  fabric.

## Switch identifiers

- Switch serial numbers, the switch MAC OUI, and the RouterOS login are omitted.
- References to the file that holds the switch credentials are omitted. The guide says
  "credentials" where the notes named a file.
- Physical port numbers on our campus switches (which uplink, which patch) are omitted;
  the RSTP discussion refers to "the campus uplink" and "an RJ45 patch".
- The campus network controller, the firewall, and their vendors, versions and addresses
  are omitted.

## Container images and repositories

- Locally built image tags (the names we gave the patched vLLM builds) are omitted,
  because they are not on any registry and would not resolve. The guide describes the
  patch chain generically and credits the public GitHub repositories by name.
- One community-published Docker Hub image is referred to as "the image published by
  the recipe author; see the repo" rather than by account name.
- Internal script names, launcher environment-variable interfaces, results-log paths and
  memory-file names were replaced with the commands and flags they wrap.

## People, clients and business detail

- Fleet-wide credentials, the fact that some hosts share credentials, and which do not,
  are omitted.
- Names of individuals other than the firm's principal are omitted, including a
  colleague's launcher scripts and address expectations.
- No client or engagement detail existed in the source material for this topic; none
  appears here. The firm's compliance work is described only in the "About us" paragraph
  of the README.
- Purchase-decision discussion (which unit to buy next, inventory, margins, order
  velocity, supplier costs) is omitted except for the list prices of GB10 units observed
  in June 2026 and the breakout DAC price, both dated in the bill of materials.
- Operational incidents unrelated to the fabric (voice systems, chat bridges, unrelated
  outages, download throttling on one site's uplink) are omitted; the last of these
  survives only as the generic advice to pull images where bandwidth is good and fan
  them out over the fabric.

## What was not changed

- Every measured number (bandwidths, tokens per second, KV-cache sizes, boot times,
  memory floors, counter deltas) is exactly as logged.
- Interface and RDMA device names (`enp1s0f0np0`, `enP2p1s0f0np0`, `rocep1s0f0`,
  `roceP2p1s0f0`) are NVIDIA-documented and appear unchanged.
- RouterOS interface names (`qsfp56-dd-1-1`, `qsfp56-2-1`, `ether1`, `ether2`) are the
  switch's own names and appear unchanged; which physical uplink is `ether1` versus
  `ether2` on each switch is arbitrary and was kept for readability.
- Community repository names, Hugging Face checkpoint names, part numbers, product
  prices and NVIDIA documentation URLs are unchanged.

## Grep used before publication

The tree was searched for internal address prefixes, internal hostnames, switch serial
prefixes, the switch MAC OUI, and the word for a login secret. The search returned no
hits at commit time. Re-run it after any edit that pastes from internal notes.
