# 10. WireGuard on the Gateway, configured by Ansible

Date: 2026-09-30

## Status

Accepted

## Context

Testers reach the private network through the Gateway. The first version of the
Gateway stack opened udp/1194 for OpenVPN. Hetzner also has a WireGuard app image.
Testers do not connect from networks that block UDP, and they do not need MFA or a
central identity login for the tunnel.

## Decision

The Gateway runs WireGuard on udp/51820, on the stock `ubuntu-24.04` image.
Ansible configures it. The Gateway's WireGuard private key is kept in SSM Parameter
Store as a SecureString, outside the server, so that a rebuild does not change it.

## Considered Options

- **OpenVPN.** Rejected because it adds a PKI with expiring certificates, and we
  do not need its TCP/443 transport or MFA. It is the fallback if these needs
  appear.
- **Hetzner WireGuard app.** Rejected because it needs a person to answer
  prompts at the first root login, so a rebuild cannot run unattended. It also
  adds a public web UI on 443 that has had no release since January 2024, and its
  nftables rules let every peer reach everything.

## Consequences

- Every Tester config holds the Gateway's WireGuard public key. If the key in SSM
  is lost or replaced, every Tester needs a new config.
- The key is created once, by hand, outside the rebuild cycle. It has the same
  lifetime as the Egress IP (ADR-0009), not the server's.
