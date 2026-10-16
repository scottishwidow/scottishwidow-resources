# 16. The Sinkhole runs in rootless Podman on the Sensor, behind a static DNAT

Date: 2026-10-16

## Status

Accepted

## Context

Containment drops every new outbound connection from a Honeypot. When an
attacker in a Cowrie session runs `wget`, the download fails and the attack
chain stops. Suricata then sees only the first packets of the download.

ADR-0013 says to add a sinkhole in a separate change and not to open
Containment. It also says that the attacker cannot reach the Sensor. A sinkhole
is a service that talks to traffic the attacker controls, so it changes that
statement.

The Honeypots have no resolver. Docker gives the Cowrie container `8.8.8.8` as
its resolver, and loaders often use a literal IP in the URL.

## Decision

- **CoreDNS and nginx are the Sinkhole.** CoreDNS answers every `A` query with
  `198.51.100.1` (TEST-NET-2) and every `AAAA` query with no answer. nginx
  answers every path and method on HTTP and HTTPS with `200`, one fixed body
  that holds the marker `honeynet-sinkhole`, and `application/octet-stream`.
- **The Sinkhole runs on the Sensor in rootless Podman**, with Quadlet units
  and pasta networking. Each container has its own user and network
  namespace. The containers publish high ports on the Sensor private IP.
- **A static DNAT in the Sensor user data** sends new connections from the
  Honeynet network to an address outside it on `tcp 80`, `tcp 443` and
  `udp/tcp 53` to the Sinkhole ports on `10.20.0.2`. The `input` chain accepts
  those ports from the Honeynet network only.
- **The `input` chain queues the Sinkhole flows**:
  `ip saddr $honeynet ct status dnat queue num 0 bypass`, before the
  established rule, as in the `forward` chain (ADR-0014).
- **Ansible generates one self-signed certificate** for nginx and keeps it
  across runs.
- **Only HTTP, HTTPS and DNS go to the Sinkhole.** TFTP and FTP are a separate
  change.

INetSim is not used. Its last release is from 2020, and ADR-0015 removed
Dionaea for the same reason. CoreDNS and nginx are maintained and have official
images.

Rootful Docker is not used. It writes iptables rules and sets the iptables
`FORWARD` policy to `drop`, which can drop the forwarded honeypot flows. The
Sensor's `flush ruleset` also removes its rules. This contradicts ADR-0010.
Rootless Podman writes no packet filter rules.

Host packages without containers are not used, because they give the Sinkhole no
separate network namespace.

The DNS answer is outside the Honeynet, so a hostname and a literal IP take the
same DNAT path.

## Consequences

- ADR-0013 still applies, with a narrower statement: the attacker cannot reach
  the host namespaces of the Sensor. The attacker can reach the Sinkhole
  containers on the Sensor, as they can reach the allowlist proxy.
- Containment does not change. A DNAT'd connection goes to the `input` chain
  and never leaves the Honeynet. The Containment counter does not count it.
- When the Sinkhole is stopped, the DNAT stays and the Sensor refuses the
  connection. Nothing leaves the Honeynet. There is no variable to turn the
  Sinkhole off.
- Suricata sees the Sinkhole flows in IDS mode through af-packet, and in IPS
  mode through the `input` queue rule. They fail open in the same way as the
  forwarded flows.
- Cowrie stores the Sinkhole body as the downloaded file. Its SHA-256 belongs
  to the Sinkhole, not to the attacker's payload. The Honeynet still collects
  no malware samples.
- A change to the DNAT or the `input` rules replaces the Sensor. After the
  replacement, run `make configure` again.
