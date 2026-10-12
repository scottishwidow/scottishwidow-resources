# 15. OpenCanary replaces Dionaea, and port 445 becomes a Dark Port

Date: 2026-10-12

## Status

Accepted

## Context

ADR-0013 says that the Honeynet collects no malware samples, and names Dionaea
as the honeypot that answers ports 21, 80, 445, 1433 and 3306 with payload
downloads disabled.

Dionaea is dead. The last commit to `DinoTools/dionaea` is from February 2021,
and the repository has 65 open issues. Two risks follow:

- Dionaea is C with the `libemu` shellcode emulator. A remote code execution in
  it, and then an escape from its container, defeats Containment on a host that
  must never attack another network. This is the risk that can cost the Hetzner
  account.
- A 2021 emulator answers a 2026 scanner wrongly. The traffic is then less
  representative, and the ET Open rules fire on the wrong things. This is the
  risk to the purpose of the Honeynet, which is Suricata practice.

A replacement must be maintained, must have an image on a registry that the
allowlist proxy already permits, and must not write the host packet filter,
because ADR-0010 gives user data that job.

Four candidates were examined:

- **OpenCanary** (Thinkst, BSD-3): maintained, Python and Twisted, official
  image `thinkst/opencanary` on Docker Hub, real modules for FTP, HTTP, MSSQL
  and MySQL.
- **Glutton** (MIT): the richest protocol set, and commits every week. It needs
  TPROXY, `iptables -t mangle`, the host network namespace and `NET_ADMIN`, so
  the container would rewrite the Honeypot host packet filter. It publishes no
  image.
- **Beelzebub** (GPL-3): maintained, official image. Its TCP lures answer with a
  banner and canned replies only, which is less than OpenCanary emulates. Its
  main feature is a shell backed by a language model, which is out of scope.
- **qeeqbox/honeypots** (AGPL-3): ten months since the last commit, and no
  published image. No better maintained than Dionaea for this purpose.

No maintained project emulates SMB. The OpenCanary `smb` module is not an
emulator. It reads the audit log of a real Samba server.

## Decision

- **OpenCanary replaces Dionaea.** It runs in its own Docker Compose project on
  the Honeypot, separate from Cowrie, so that one honeypot can be replaced
  without touching the other.
- **Four modules are enabled**: `ftp`, `http`, `mysql` and `mssql`. The seven
  forwarded ports do not change, so the Sensor is not replaced.
- **Port 445 becomes a Dark Port.** The Sensor still forwards it, and no service
  answers it. The Honeypot input chain drops the packet, so the port times out.
- **The container binds no privileged port.** `honeypot_port_redirects` gains
  `21` and `80`, and the OpenCanary config uses the matching high ports.
  The container keeps `cap_drop: ALL` and `read_only: true`.
- **Bridge networking with published ports**, as Cowrie uses. Not the host
  network namespace that the upstream Compose file uses.
- **The HTTP module logs unimplemented methods and redirects.** Both are off by
  default.

OpenCanary is chosen because it is the only candidate that is maintained, has an
image on an allowlisted registry, emulates four of the five protocols, and
removes a memory-unsafe shellcode emulator from a contained host.

Glutton is not chosen, although it has the best protocol coverage, because a
container that writes the Honeypot packet filter contradicts ADR-0010 and fights
the forward rules in the Honeypot user data.

Real Samba is not installed for port 445. It would put a real file-sharing
service on the Honeypot, which is a larger escape surface than the Dionaea that
this ADR removes.

There are still no malware samples. OpenCanary has no download handler to
disable. Each module stops at the credential prompt.

## Consequences

- Payload URLs are lost for FTP, MySQL and MSSQL. OpenCanary records the source
  address, the time, the banner exchange and the credentials, and nothing after
  authentication fails.
- This is acceptable, because the Sensor is inline. Suricata sees the whole
  exploit on the wire however little the honeypot writes down. The job of the
  honeypot here is to complete the handshake, so that the exploit is sent at
  all. Suricata is what records it.
- Port 445 reads as `filtered`, not `closed`, to a scanner. This is deliberate.
- Suricata still inspects the Dark Port traffic. ADR-0014 queues every packet of
  a DNAT'd flow, and the Sensor forwards 445, so the SYN reaches queue 0.
- `make verify` checks six ports that answer and one that times out, not seven
  that answer.
- The services claim old versions, `Apache/2.2.22 (Ubuntu)` and MySQL
  `5.5.43`. Old versions attract exploit attempts for old CVEs. The pairing is
  fingerprintable as a honeypot, which is accepted.
- A new service means a new forwarded port, a Hetzner firewall rule and a Sensor
  replacement. It is a separate issue.
