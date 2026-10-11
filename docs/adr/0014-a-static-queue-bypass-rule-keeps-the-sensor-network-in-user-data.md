# 14. A static `queue bypass` rule keeps the Sensor network in user data

Date: 2026-10-10

## Status

Accepted

## Context

Suricata on the Sensor has two modes. In IDS mode it reads a copy of the
traffic with af-packet and cannot block. In IPS mode it reads NFQUEUE 0 and
gives a verdict on each packet. One Ansible variable changes the mode.

ADR-0010 says that user data owns sysctl and the complete, static nftables rule
set, and that Ansible never writes them. If the IPS mode needs a different
forward rule, Ansible must write nftables, or each mode change must replace the
Sensor.

When a rule sends packets to a queue that nothing reads, nftables drops them.
Without a change, the Honeypots are not reachable in IDS mode or when Suricata
is stopped.

## Decision

The Sensor user data
(`live/hetzner/honeynet/sensor/cloud-init.yaml.tftpl`) has one static forward
chain for both modes:

1. Containment: drop new connections from the Honeynet network to anywhere
   outside it.
2. Send all packets of the forwarded honeypot flows (`ct status dnat`) to
   `queue num 0 bypass`.
3. Allow established and related traffic.

The queue rule comes before the established rule, so that in IPS mode Suricata
gets every packet of a flow. If it came after, Suricata would see only the first
packet of each connection.

Because of `bypass`, a packet passes when nothing reads queue 0. The Sensor fails
open.

The Sensor does not masquerade. Conntrack reverses the DNAT on the replies, so
they leave with the Sensor public IPv4 as the source. A Honeypot has no new
outbound connection to masquerade.

## Consequences

- A change between IDS and IPS mode changes only the Suricata config. It does
  not change nftables and does not replace the Sensor.
- When Suricata is stopped, or reads af-packet in IDS mode, the Honeypots stay
  reachable. No `drop` rule applies until Suricata reads the queue again.
- Containment still applies when the Sensor fails open, because it is the first
  forward rule and does not depend on the queue.
- Ansible stops if forwarding, DNAT, Containment or the queue rule is missing.
  It only reads them.
- A new honeypot port goes in the Sensor root and replaces the Sensor. After the
  replacement, run `make configure` again.
