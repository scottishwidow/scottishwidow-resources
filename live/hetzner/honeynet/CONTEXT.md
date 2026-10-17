# Honeynet

The `honeynet` environment: hosts that invite attacks so that Suricata has real hostile traffic to inspect. It is hostile by design and shares nothing with the other environments.

## Language

**Honeynet**:
The isolated set of hosts that attract and observe attacks. It has its own Hetzner project, network and SSH key, and no path to any other environment.
_Avoid_: Lab, sandbox, DMZ

**Honeypot**:
A host with no public IP that runs emulated services to attract attacks. Nothing on it is trusted.
_Avoid_: Decoy, trap, target

**Persona**:
The one host identity that every Honeypot service claims: hostname, OS, kernel and service versions. It is Ubuntu 22.04.
_Avoid_: Profile, disguise, cover

**Dark Port**:
A honeypot port that the Sensor forwards although no service answers it. Suricata still inspects the traffic.
_Avoid_: Closed port, filtered port, unused port

**Sensor**:
The single Honeynet host with a public IPv4. Every packet between the internet and a Honeypot passes through it, and Suricata on it inspects them.
_Avoid_: Gateway, router, firewall, IDS box

**Containment**:
The rule that no new connection leaves a Honeypot for the internet. Replies to inbound connections are allowed.
_Avoid_: Data control, egress filtering, sandboxing

**Sinkhole**:
The fake internet service that answers a Honeypot's outbound HTTP, HTTPS and DNS in place of the real destination. A connection to the Sinkhole never leaves the Honeynet, so Containment still holds.
_Avoid_: Fake internet, INetSim, egress proxy
