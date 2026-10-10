# OVPN

The `ovpn` Hetzner Cloud environment: a private network of hosts reached through one public entry point.

## Language

**Gateway**:
The single host with a static public IPv4 that is the VPN entry point to the private network and the NAT exit for all Private Hosts.
_Avoid_: Bastion, NAT instance, VPN box, OpenVPN server

**Private Host**:
A host attached only to the private network, with no public IPv4 or IPv6.
_Avoid_: Internal VM, backend server
