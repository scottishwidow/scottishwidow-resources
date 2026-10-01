# 11. VPN clients are masqueraded into the private network

Date: 2026-10-01

## Status

Accepted

## Context

VPN clients get addresses from `10.8.0.0/24`, which is not part of the private
network. A Private Host must send its replies to a VPN client back through the
Gateway. Two options:

- Route `10.8.0.0/24` to the Gateway in the Hetzner network, and allow that
  range in the input rules of each Private Host.
- Masquerade VPN client traffic on the Gateway, also into the private network.

## Decision

The Gateway masquerades all traffic from the VPN network. The Private Hosts see
the Gateway private IP (`10.10.0.2`) as the source.

## Consequences

- The Private Hosts need no rule change. Their input rule accepts only the
  Gateway.
- The Hetzner network needs no extra route.
- A Private Host cannot tell one VPN client from another, or a VPN client from
  the Gateway. To log or filter by client, look at the Gateway, or replace this
  decision with the route option.
