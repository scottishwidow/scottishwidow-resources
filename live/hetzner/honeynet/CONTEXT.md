# Honeynet

The `honeynet` environment: hosts that invite attacks so that Suricata has real hostile traffic to inspect. It is hostile by design and shares nothing with the other environments.

## Language

**Honeynet**:
The isolated set of hosts that attract and observe attacks. It has its own Hetzner project, network and SSH key, and no path to any other environment.
_Avoid_: Lab, sandbox, DMZ

**Honeypot**:
A host with no public IP that runs emulated services to attract attacks. Nothing on it is trusted.
_Avoid_: Decoy, trap, target

**Sensor**:
The single Honeynet host with a public IPv4. Every packet between the internet and a Honeypot passes through it, and Suricata on it inspects them.
_Avoid_: Gateway, router, firewall, IDS box

**Containment**:
The rule that no new connection leaves a Honeypot for the internet. Replies to inbound connections are allowed.
_Avoid_: Data control, egress filtering, sandboxing
