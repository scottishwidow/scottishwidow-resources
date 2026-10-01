# 12. The OpenVPN PKI lives only on the Gateway

Date: 2026-10-01

## Status

Accepted

## Context

The OpenVPN CA, server key and client keys must exist somewhere. If they live
outside the Gateway, client configs survive a Gateway recreate, but a secret
store (for example AWS SSM) and a delivery step are necessary. Cloud-init user
data is not an option: Terraform state keeps it and the metadata service
exposes it.

## Decision

The `openvpn` Ansible role creates the PKI on the Gateway with Easy-RSA. The PKI
exists only there. Ansible copies the client configs to the workstation, in
`live/hetzner/ansible/clients/` (not in Git).

## Consequences

- No secret store and no secret in Terraform state.
- A Gateway recreate deletes the PKI. Run `make configure` and give each client
  its new config. The public IP stays (ADR-0009), but the old configs do not
  work.
- To keep client configs across recreates, move the PKI to a secret store and
  replace this decision.
