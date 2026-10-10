# 13. Suricata runs on an inline Sensor, and the Sensor enforces Containment

Date: 2026-10-10

## Status

Accepted

## Context

The Honeynet exists to practice Suricata on real hostile traffic. A Honeypot
attracts attacks, so we must expect that an attacker gets control of it. A
controlled Honeypot that scans or attacks other networks, or that hosts malware,
is a reason for Hetzner to lock the account.

Suricata needs to see the traffic between the internet and the Honeypots. Three
options:

- Run Suricata on the Honeypot.
- Copy the traffic to a separate sensor with AWS traffic mirroring.
- Put a Sensor inline, so that every packet between the internet and a Honeypot
  goes through it.

## Decision

- The Sensor holds the only public IPv4 of the Honeynet. It forwards the
  honeypot ports to `honeypot-1` with DNAT and keeps the source address. The
  Honeypots have no public IP. Their default route goes to the Sensor.
- Suricata runs on the Sensor.
- The Sensor enforces default-deny Containment. The first forward rule drops
  every new connection from the Honeynet network to an address outside it.
  Replies to inbound connections pass. Package and image updates go through an
  allowlist proxy on the Sensor.
- The Honeynet collects no malware samples. Dionaea does not download payloads.

Suricata is not on the Honeypot, because an attacker who controls the Honeypot
can stop Suricata, change its rules or change its logs. The Sensor is a host
that the attacker cannot reach.

AWS traffic mirroring is not used. It copies traffic out of band, so the sensor
cannot block a packet and cannot enforce Containment. It also puts the
Honeynet in the same AWS account as the Management environment.

There are no malware samples, because hosting malware is a reason for Hetzner to
lock the account. A sample on disk can also escape through a mistake. The
payload URLs in the logs are sufficient to practice detection.

## Consequences

- Containment does not depend on Suricata. It applies in IDS and IPS mode, and
  when Suricata is stopped.
- A Honeypot cannot reach the internet directly, not even for DNS. It gets
  updates only through the proxy.
- Suricata in IPS mode can drop attack traffic, because it is in the packet
  path (ADR-0014).
- The Sensor is a single point of failure. When it is down, no Honeypot is
  reachable.
- To study what malware does after a download, add a sinkhole such as INetSim
  in a separate change. Do not open Containment.
