# 9. The Gateway's public IP outlives the server

Date: 2026-09-29

## Status

Accepted

## Context

Every VPN client config hard-codes the Gateway's public IPv4. Hetzner replaces a
server when its image or type changes, and the IP that comes with the server goes
away with it. A rebuild would then make every client config invalid.

## Decision

The Gateway's public IPv4 is a separate `hcloud_primary_ip` with
`auto_delete = false` and `delete_protection = true`, assigned to the server.
The server does not get the IP that Hetzner creates with it. There is no public
IPv6.

## Consequences

- Terraform can replace the Gateway server and the IP stays the same.
- To delete the IP, first set `delete_protection = false` and apply.
- The IP costs money while no server has it.
