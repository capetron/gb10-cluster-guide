# 02. Two nodes and three nodes: the switchless configurations

**Summary.** NVIDIA supports two switchless topologies for GB10 workstations: two units
joined by one QSFP cable, and three units joined by three cables in a ring, each unit
using both of its QSFP ports. Both are covered by official NVIDIA playbooks and both are
what the cluster cable was made for. Three is the switchless ceiling because each unit
has exactly two ports; a fourth unit needs a switch (see [03-switched-fabric.md](03-switched-fabric.md)).
This document covers the physical connection, addressing that survives reboots, jumbo
frames, how to prove the link is healthy before you start a model, and why bonding the
two PCIe halves of a port does not do what people expect.

## Two units: one cable

NVIDIA's "Connect Two Sparks" playbook describes "high-speed inter-node communication
using 200GbE direct QSFP connections" with one QSFP cable. Prerequisites from the
playbook: two systems, SSH access to both, root or sudo on both, the same username on
both, key-based SSH between them with no interactive prompt. NVIDIA rates it at one hour including validation,
medium risk, and reversible by removing the netplan configuration. NVIDIA also ships a
`discover-sparks.sh` script for node discovery and SSH key distribution, and a Sync
Cluster Assistant that does discovery, validation and SSH setup automatically.

Physically: one cable from Port 0 on the first unit to Port 0 on the second. Port 0 is
the left QSFP port, nearest the RJ45 jack. Which port you pick does not matter for
bandwidth; it matters for consistency in the interface names below.

What you get from one cable: one 200 Gb/s link made of two 100 Gb/s PCIe halves. Every
procedure below configures both halves. If you configure only `enp1s0f0np0` you will
measure about 111 Gb/s and wonder where the other half went.

Cable: https://petronellatech.com/hardware/dgx-spark-cluster-cable/

## Three units: a ring of three cables

NVIDIA's "Connect Three DGX Spark in a Ring Topology" playbook uses "three QSFP cables
for direct 200GbE connection" between three systems. Each unit uses both of its QSFP
ports: Port 1 of unit A to Port 0 of unit B, Port 1 of B to Port 0 of C, Port 1 of C to
Port 0 of A. Every unit has a direct link to every other unit, so this is a full mesh,
not a bus. Prerequisites match the two-node playbook plus current OS and firmware on all
three.

This is the switchless ceiling. With two ports per unit, a fourth unit cannot reach every
other unit directly; you can wire four units as four point-to-point links, but then two
of the units have no direct path to each other. We built exactly that with four units and
/30 links before we bought the switch and confirmed there was no route between the two
non-adjacent units. All-to-all over four needs three links per node, and the hardware has
two. Four or more means a switch.

Three cables: https://petronellatech.com/blog/dgx-spark-cluster-cables-in-stock-0-5m-qsfp112-400g-dac-for-every-gb10-workstation-159-shipped/

## Addressing

Two schemes work. Both use the same rule: **one subnet per PCIe half, and never a default
route on the fabric interfaces.**

### Point-to-point /30s (two nodes, or the three-node ring)

Give each cable its own /30 for the first half and a second /30 for the second half. The
scheme we used put the second half ten higher in the third octet, so it is obvious at a
glance which half you are looking at:

| Link | First half (`enp1s0fXnpX`) | Second half (`enP2p1s0fXnpX`) |
|---|---|---|
| gb10-01 to gb10-02 | 198.51.100.0/30 | 203.0.113.0/30 |
| gb10-01 to gb10-03 | 198.51.100.4/30 | 203.0.113.4/30 |
| gb10-02 to gb10-03 | 198.51.100.8/30 | 203.0.113.8/30 |

(198.51.100.0/24 and 203.0.113.0/24 are RFC 5737 documentation ranges; substitute your own
private ranges.)

### Flat planes (what we moved to for the switch, and what we would use again for three)

One /24 per half, one host number per unit. Half A of every unit is `198.51.100.N/24`,
half B is `203.0.113.N/24`, and N is the unit number. This is the scheme we run on the
switched fabric and it is simpler to reason about than /30s even without a switch; it
also means the addressing does not change when you add the switch later.

### Making it persist

This is where most of our early time went. Fabric addresses that live only in a running
kernel do not survive a reboot, and a unit that reboots into the wrong address on the
wrong link is the third most common fault we hit. Two mechanisms, depending on the
vendor:

**DGX Spark Founders Edition (netplan, systemd-networkd).** Drop a file such as
`/etc/netplan/40-cx7.yaml`:

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    enp1s0f0np0:
      addresses: [198.51.100.5/24]
      mtu: 9000
      link-local: []
      dhcp4: false
      dhcp6: false
    enP2p1s0f0np0:
      addresses: [203.0.113.5/24]
      mtu: 9000
      link-local: []
      dhcp4: false
      dhcp6: false
```

`netplan apply` did not drop our management SSH session. Remove any older netplan
fragments that still assign the old direct-attach addresses to the same interfaces, and
back the directory up first. On the DGX Spark the fabric NICs show as `unmanaged` in
NetworkManager, which is correct: networkd owns them.

**MSI EdgeXpert (NetworkManager).** One profile per half, IPv6 off, never a default
route, MTU 9000:

```
nmcli con add type ethernet ifname enp1s0f0np0 con-name fabric-a \
  ipv4.method manual ipv4.addresses 198.51.100.1/24 ipv4.never-default yes \
  ipv6.method disabled 802-3-ethernet.mtu 9000
nmcli con add type ethernet ifname enP2p1s0f0np0 con-name fabric-b \
  ipv4.method manual ipv4.addresses 203.0.113.1/24 ipv4.never-default yes \
  ipv6.method disabled 802-3-ethernet.mtu 9000
```

Then the trap that cost us a launch: **an old profile that is carrier-down can still hold
an address and still own a route.** When we retired a direct-attach bond, the bond
interface with no carrier kept its old /30 and the kernel routed the first four addresses
of the new /24 into it. Ping to the fifth address worked; ping to the second and third
failed. `nmcli con down <old-profile>` fixed it; setting the old profiles to
`autoconnect no` keeps it fixed. Audit with `ip route` after every change; every fabric
route should point at a fabric interface with carrier.

## MTU 9000

Set `mtu 9000` on every fabric interface on every unit. There is no negotiation to save
you: a 1500-byte interface on one end of a 9000-byte link silently fragments or drops
large frames and NCCL bootstraps then stalls. Verify with a jumbo ping that forbids
fragmentation:

```
ping -M do -s 8972 -c 3 198.51.100.2
```

8972 is 9000 minus the 20-byte IP header and 8-byte ICMP header. A clean reply from every
unit on both planes means MTU is right end to end. When a unit later joins a switch, the
same ping proves the switch path too (see [03-switched-fabric.md](03-switched-fabric.md)
for the switch-side l2mtu that must also be set).

## Link checks before you start a model

Run these in order. Each one rules out a class of fault the next one would misreport.

1. **Link state and speed.** On each unit, `ethtool enp1s0f0np0 | grep -E 'Speed|Link'`
   should show 200000Mb/s and Link detected: yes on both halves. This proves the cable
   and the NIC negotiated. It does not prove throughput (see item 4).
2. **Addresses and routes.** `ip -br addr show enp1s0f0np0 enP2p1s0f0np0` and `ip route`.
   Two addresses, two routes, no default route on either, no stale routes into interfaces
   without carrier.
3. **Jumbo ping on both planes**, as above.
4. **RDMA bandwidth, one half at a time, then both.** This is the only test that catches
   a power-throttled NIC or a CPU-forwarded path. Full commands and expected numbers are
   in [04-validation.md](04-validation.md). Expect about 111 Gb/s per half on a direct
   cable and about 196 Gb/s with both halves running concurrently. If a half reads
   12 to 13 Gb/s with everything else green, update the OS and firmware and reboot before
   doing anything else.
5. **Peer firewall.** If a host firewall is on, multi-node vLLM needs full peer
   connectivity, not just the rendezvous port: the collective bootstrap opens dynamic
   ports and the head node also connects to its own address. Allow both fabric subnets
   from every peer, including the unit itself.
6. **Same container image digest everywhere.** Two units pulling "the same" nightly tag
   on different days got different NCCL builds, and the symptom was a bootstrap warning
   about a message truncated by four bytes that looked exactly like a network fault. Pin
   the digest.

## What a bond does not give you

People bond the two halves of a port because two interfaces on one wire look like a
classic active-active pair. Three things to know before you do:

1. **RDMA bypasses the bond.** NCCL and `ib_write_bw` talk to the RDMA devices
   (`rocep1s0f0`, `roceP2p1s0f0`), not to the bonded Ethernet interface. NCCL uses both
   halves on its own when you list both in `NCCL_IB_HCA`. A bond adds nothing to the path
   that carries the model's traffic.
2. **TCP does not fill even one half.** A single TCP stream on the GB10's ARM cores sits
   near 12 Gb/s. Bonding two halves does not make one stream faster; at best it lets many
   streams spread. If you need TCP throughput for weight distribution, use many parallel
   streams (we fan out weights with `tar | ssh` at about 830 MB/s over the fabric, which
   is a single stream with a large block size and works well enough).
3. **The bond is the thing that keeps stale state.** Our carrier-down bond holding an old
   address and a live route (above) is the direct consequence of having a bond at all.
   Two plain interfaces with two plain addresses have no such failure mode.

The one place the second half matters for plain IP is NCCL's socket bootstrap, which uses
one Ethernet interface (`NCCL_SOCKET_IFNAME=enp1s0f0np0`). It only needs to exist and
route; it does not need to be fast.

## What sharding over the wrong network costs

We measured this once so you do not have to. The same dense 27B FP8 model, same pinned
image, same flags:

| Configuration | Prefill | Decode |
|---|---|---|
| 1 unit, tensor parallel 1 | 1,963 tok/s | 8.3 tok/s |
| 4 units, tensor parallel 4, over 10 Gb/s Ethernet | 539 tok/s | 3.5 tok/s |

Three extra units over the management LAN made prefill 3.6x slower and decode 2.4x
slower. Tensor parallel is only worth running over the RDMA fabric at line rate, and only
for models whose per-rank working set shrinks enough to pay for the collectives. The
four-node results that do work are in [05-serving-models.md](05-serving-models.md).

## Sources

- NVIDIA, Connect Two Sparks: https://build.nvidia.com/spark/connect-two-sparks
  (one QSFP cable, prerequisites, netplan, discover-sparks.sh, duration and risk)
- NVIDIA, Connect Three DGX Spark in a Ring Topology: https://build.nvidia.com/spark/connect-three-sparks
  (three QSFP cables, ring, prerequisites)
- NVIDIA DGX Spark User Guide, ConnectX-7 Networking: https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html
  (direct cable up to 3 systems, switch for 4, interface names, Sync Cluster Assistant)
- Petronella Technology Group, Inc., cable product page (three-node ring FAQ):
  https://petronellatech.com/blog/dgx-spark-cluster-cables-in-stock-0-5m-qsfp112-400g-dac-for-every-gb10-workstation-159-shipped/
- Our notes, 2026-08-15 (four-unit /30 ring with no route between non-adjacent units; 1,963 / 8.3 versus 539 / 3.5 tok/s; 12 Gb/s single-stream TCP; digest drift; host firewall full-mesh requirement), 2026-08-28 (NetworkManager profiles, carrier-down bond trap, MTU 9000, jumbo ping 8972), 2026-08-31 (DGX Spark netplan file, networkd renderer, unmanaged in NetworkManager)
