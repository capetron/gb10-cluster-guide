# 03. The switched fabric: MikroTik CRS812 for four or more GB10 workstations

**Summary.** Four or more GB10 workstations need a 200G-capable switch. We built a
six-node fabric on two MikroTik CRS812-8DS-2DQ-2DDQ-RM switches running RouterOS 7.24.1:
four MSI EdgeXpert units on the first switch through both of its QSFP56-DD ports broken
out to 2 x 200G each, two DGX Spark Founders Edition units on the second switch through
one breakout, and a 200G inter-switch link (ISL) on the native QSFP56 ports. It runs
RoCE at 196 Gb/s per node through the switch ASIC with no PFC or ECN tuning. Getting there
required four non-obvious steps, each of which cost us a session: the DD breakout must be
forced to 200G-baseCR4 on the lane-master interfaces because it does not auto-negotiate;
l2mtu must be raised on the switch ports, not just on the hosts; two switches that both
uplink to your campus network will have their ISL blocked by RSTP and silently detour
fabric traffic over the campus path; and putting the fabric in a second bridge to fix
that drops throughput from 196 Gb/s to under 5 Gb/s because this switch chip
hardware-offloads only one bridge. This document gives the configuration that works,
the traps in the order we hit them, and the trade-off we accepted. NVIDIA's own switch
playbook covers up to four systems; six on two switches is our measured configuration,
not an NVIDIA-supported one.

## Topology

```
                     crs812-a                              crs812-b
             +----------------------+              +----------------------+
  gb10-01 ---| qsfp56-dd-2-5 (200G) |              | qsfp56-dd-1-1 (200G) |--- gb10-05 (DGX Spark FE)
  gb10-02 ---| qsfp56-dd-2-1 (200G) |              | qsfp56-dd-1-5 (200G) |--- gb10-06 (DGX Spark FE)
  gb10-03 ---| qsfp56-dd-1-5 (200G) |              | qsfp56-dd-2-x  (free, pre-configured)
  gb10-04 ---| qsfp56-dd-1-1 (200G) |              |                      |
             |                      |              |                      |
             | qsfp56-2-1 =========== 200G ISL ===== qsfp56-2-1           |
             |                      |              |                      |
             | ether2 --> campus    |              | ether1 --> campus (RSTP cost raised)
             +----------------------+              +----------------------+

  Each gb10-NN: one 0.5 m QSFP112 DAC from its QSFP Port 0 into one QSFP56 leg of a
  QSFP56-DD to 2 x QSFP56 breakout DAC. Host half A = 198.51.100.NN/24, half B = 203.0.113.NN/24.
```

Switch inventory per CRS812-8DS-2DQ-2DDQ-RM: 2 x 400G QSFP56-DD, 2 x 200G QSFP56,
8 x 50G SFP56, 2 x 10G RJ45. Each DD port breaks out to two 200G legs, so one switch
serves four nodes on breakouts plus two more on the native QSFP56 ports (six at 200G if
you do not need an ISL). With two switches and the native ports used for the ISL, the
fabric is provisioned for eight nodes on breakouts, of which we populate six.

Breakout cables: NADDOD Q2Q56-400G-CU1 (QSFP-DD to 2 x QSFP56, MikroTik-coded). Node
cables: the same 0.5 m QSFP112 DAC used for direct attach. ISL: one QSFP56 200G DAC
between the native ports. See [06-bill-of-materials.md](06-bill-of-materials.md).

## Step 1: force the DD breakout to 200G-baseCR4 (it does not auto-negotiate)

This is the part nobody documents. With a breakout DAC plugged into a QSFP56-DD port, the
CRS812 detects the cable but reports auto-negotiation failed and no link on the legs. The
QSFP56-DD ports do not auto-negotiate 2 x 200G. Per MikroTik's compatibility notes, set
the speed explicitly on the **lane-master** interfaces of each DD port, which are lane 1
and lane 5:

```
/interface/ethernet
set qsfp56-dd-1-1 auto-negotiation=no speed=200G-baseCR4
set qsfp56-dd-1-5 auto-negotiation=no speed=200G-baseCR4
set qsfp56-dd-2-1 auto-negotiation=no speed=200G-baseCR4
set qsfp56-dd-2-5 auto-negotiation=no speed=200G-baseCR4
```

Within about ten seconds all four legs on the first switch came up link-ok at 200 Gbps
with FEC91. The same four lines on the second switch brought the DGX Spark legs up in
seconds, including the two legs of the not-yet-populated second DD port, so a future
breakout plugs in with no switch change.

Verify: `/interface/ethernet/monitor qsfp56-dd-1-1 once` should show `status: link-ok`,
`rate: 200Gbps`, `fec: fec91`. (The same values are available over the RouterOS REST API
with a POST to `/rest/interface/ethernet/monitor` and body `{"numbers":"qsfp56-dd-1-1","once":""}`,
which is how we scripted the checks.)

## Step 2: l2mtu 9216 and mtu 9000 on the fabric ports and the ISL

Hosts at MTU 9000 are not enough. The switch port's layer-2 MTU must admit the frame, and
on the CRS812 the hardware-offloaded forwarding path uses the **port** l2mtu, not the
bridge's:

```
/interface/ethernet
set qsfp56-dd-1-1,qsfp56-dd-1-5,qsfp56-dd-2-1,qsfp56-dd-2-5,qsfp56-2-1 l2mtu=9216 mtu=9000
```

Setting l2mtu bounces the link for a few seconds; harmless. The bridge interface itself
keeps l2mtu 1584 because it takes the minimum of its member ports and the RJ45 ports are
members; that is fine, because offloaded traffic never consults it. Prove it with the
same jumbo ping from [02-two-and-three-nodes.md](02-two-and-three-nodes.md):
`ping -M do -s 8972` between every pair of nodes on both planes. We verified it across the
whole six-node mesh.

## Step 3: the ISL, and the RSTP trap with dual uplinks

Cable the native QSFP56 ports of the two switches together and force the speed the same
way:

```
/interface/ethernet
set qsfp56-2-1 auto-negotiation=no speed=200G-baseCR4 l2mtu=9216 mtu=9000
```

The link came up link-ok. Then nothing crossed it.

Both switches also had a copper uplink into our campus network for management. That
creates a layer-2 loop: switch A to campus to switch B to ISL to switch A. RSTP did its
job and put the ISL into the **alternate (blocked)** role on the first switch. A second
RJ45 patch between the switches was blocked too. The consequence, which we did not
notice until the DGX Spark units joined the second switch: any fabric traffic between
the two switches was detouring through the campus network at 2.5 Gb/s and MTU 1500. The
symptom on the hosts was that cross-switch jumbo pings failed while same-switch jumbo
pings passed, and cross-switch RDMA measured 4.47 Gb/s.

The clean fix is topological: give the second switch **no** independent campus uplink,
so its only path to the first switch (and to management) is the ISL. We did that without
touching a cable by raising the RSTP cost of the second switch's campus uplink so far
that it re-roots through the ISL:

```
/interface/bridge/port
set [find interface=ether1] path-cost=200000000 internal-path-cost=200000000
```

After this the second switch's root port is the ISL (`qsfp56-2-1`), its campus uplink and
the RJ45 patch are both alternate (standby), and the first switch's ISL end is
designated. It is reversible configuration, and if you later pull the second uplink
physically, nothing changes. Cross-switch jumbo pings passed on both planes immediately
and cross-switch RDMA went from 4.47 to 109.08 Gb/s (see [04-validation.md](04-validation.md)).

Two notes on this:

- Management addresses should live on the **bridge** interface, not on a physical port,
  so that management follows whichever path RSTP picks. We moved both switches'
  management addresses to `bridge` deliberately during this work and kept it.
- **RSTP is VLAN-blind.** Putting the fabric in its own VLAN does not unblock an ISL that
  RSTP has blocked. Only removing the loop (or changing costs so the ISL wins) does.

## Step 4: the bridge / hardware-offload trap (196 to 5 Gb/s)

Our first attempt to isolate the fabric from the campus LAN was the textbook one: a
second bridge named `fabric` on each switch containing only the DD legs and the ISL, with
no campus uplink in it. It worked on paper. The ISL unblocked, jumbo pings passed
end to end.

Then every RDMA test on the fabric collapsed:

| Path | Before (single bridge) | After (second bridge) |
|---|---|---|
| DGX Spark pair through switch B | 109 Gb/s | 4.9 Gb/s |
| MSI pair through switch A, both halves | 196 Gb/s | 4.85 Gb/s |
| iperf3 TCP | 93 Gb/s | 8.8 Gb/s |

The sending NIC logged `packet_seq_err` and congestion notification packets, which is
loss. The cause is in MikroTik's documentation for this switch family: the Marvell
Prestera switch chip **hardware-offloads only one bridge**. A second bridge is forwarded
by the switch's CPU, which tops out in the single-digit Gb/s range and drops the rest.

We reverted: all fabric legs and the ISL back into the single main bridge, the `fabric`
bridges deleted, `hw-offload=yes` on every fabric port, and 109.2 / 109.3 Gb/s
re-verified on both pods. The RSTP cost change in Step 3 is what replaced it.

## What we settled on and the trade-off

Final state on both switches:

- One bridge per switch, hardware-offloaded, containing the DD legs, the ISL, and the
  campus uplinks.
- DD lane masters and the ISL forced to 200G-baseCR4, l2mtu 9216, mtu 9000.
- The second switch's campus uplink carries a very high RSTP path cost, so the ISL is its
  root port and the fabric crosses the ISL at 200G.
- Management addresses on the bridge interface.
- No PFC, no ECN configuration. RoCE ran at line rate without it in every test, including
  two 100G senders sharing one ISL direction (which produced congestion notifications
  and a fair split, not a collapse; see [04-validation.md](04-validation.md)).

The trade-off: the fabric subnets share the switch bridge with the campus LAN, so ARP for
the fabric planes leaks onto the management network. It is cosmetic for us. The correct
hygiene when we get to it is **VLAN filtering inside the single bridge**, which the
Prestera chip does offload, with the fabric legs and the ISL as untagged members of a
fabric VLAN and the uplinks excluded from it. That keeps one offloaded bridge and
removes the leak. It does not change the RSTP story above.

## Host side for the switched fabric

Same as [02-two-and-three-nodes.md](02-two-and-three-nodes.md), flat planes: half A of
node NN is `198.51.100.NN/24`, half B is `203.0.113.NN/24`, MTU 9000, no default route,
IPv6 off. Keep the first node's half-A address stable; every launcher in
[05-serving-models.md](05-serving-models.md) uses it as the rendezvous address.

Retire the direct-attach profiles before you plug into the switch (set them
`autoconnect no` rather than deleting them, so you can go back), and check `ip route` for
the carrier-down-bond trap described in the previous document. On the DGX Spark units,
delete the old netplan fragments that assigned the direct-attach addresses and write the
new one; we backed up `/etc/netplan/` first.

Moving a node from one switch leg to another bounces the fabric for that node. Stop any
multi-node model cleanly first; we stopped and relaunched a four-node serving run around
the lane moves and it came back in about ten minutes.

## Sanitized RouterOS configuration, in one block

```
# Lane masters of both QSFP56-DD ports: forced 200G, jumbo. Repeat on each switch.
/interface/ethernet
set qsfp56-dd-1-1 auto-negotiation=no speed=200G-baseCR4 l2mtu=9216 mtu=9000
set qsfp56-dd-1-5 auto-negotiation=no speed=200G-baseCR4 l2mtu=9216 mtu=9000
set qsfp56-dd-2-1 auto-negotiation=no speed=200G-baseCR4 l2mtu=9216 mtu=9000
set qsfp56-dd-2-5 auto-negotiation=no speed=200G-baseCR4 l2mtu=9216 mtu=9000
# Native 200G port used as the ISL.
set qsfp56-2-1   auto-negotiation=no speed=200G-baseCR4 l2mtu=9216 mtu=9000

# One bridge. All fabric legs, the ISL and the uplinks are members, hardware offload on.
/interface/bridge/port
set [find interface~"qsfp56"] hw=yes

# Management address on the bridge, not on a physical port.
/ip/address
add address=192.0.2.11/24 interface=bridge      # crs812-a
# add address=192.0.2.12/24 interface=bridge    # crs812-b

# On crs812-b only: make the ISL the root port by pricing the campus uplink out.
/interface/bridge/port
set [find interface=ether1] path-cost=200000000 internal-path-cost=200000000

# Checks
/interface/ethernet/monitor qsfp56-dd-1-1,qsfp56-dd-1-5,qsfp56-dd-2-1,qsfp56-dd-2-5,qsfp56-2-1 once
/interface/bridge/port print where interface=qsfp56-2-1     # role should be root-port on crs812-b
```

## Sources

- MikroTik CRS812-8DS-2DQ-2DDQ-RM product and compatibility documentation (port inventory; DD breakout requires forced 200G-baseCR4 on lane masters)
- MikroTik documentation, "Bridging and Switching" and "Marvell Prestera switch chip features", help.mikrotik.com (single hardware-offloaded bridge; VLAN filtering inside the bridge is offloaded)
- NVIDIA DGX Spark User Guide, ConnectX-7 Networking: https://docs.nvidia.com/dgx/dgx-spark/spark-clustering.html (switch-based connection documented for up to four systems)
- Our build notes, 2026-08-17 (order, switch inventory, wiring plan), 2026-08-28 (breakout speed forcing, l2mtu, ISL RSTP-blocked, 196 Gb/s through the ASIC), 2026-08-31 (DGX Spark join, second-bridge collapse and revert, RSTP path-cost cutover, management on bridge, 4.47 to 109.08 Gb/s cross-switch)
