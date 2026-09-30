# Hetzner

The `hetzner` Hetzner Cloud environment: the workspace of a penetration testing team. It is a private network of hosts, reached through one public entry point that is also the single source IP of the team.

## Language

### Infrastructure

**Gateway**:
The single host that holds the Egress IP. It is the VPN entry point to the private network and the NAT exit for all Private Hosts.
_Avoid_: Bastion, NAT instance, VPN box, OpenVPN server

**Private Host**:
A host attached only to the private network, with no public IPv4 or IPv6.
_Avoid_: Internal VM, backend server

**Egress IP**:
The public IPv4 of the Gateway, and the single source address the team presents to Customers.
_Avoid_: Public IP, static IP, whitelisted IP

### People and organizations

**Tester**:
A member of the penetration testing team who reaches the workspace through the VPN.
_Avoid_: Admin, user, operator, client

**Customer**:
An organization that hires the team and whitelists the Egress IP.
_Avoid_: Client, target
