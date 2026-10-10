# 10. Gateway user data owns the host network, Ansible owns OpenVPN

Date: 2026-10-01

## Status

Accepted

## Context

The Gateway needs IPv4 forwarding, an nftables rule set (input filter, forward
filter, NAT) and an OpenVPN server. Two tools can configure the host: cloud-init
user data from Terraform, and Ansible. If both tools write the same files, each
run can undo the other.

The rule set changes almost never. OpenVPN changes often and holds secret state.
A user data change replaces the Gateway, but the stack is recreated often and the
public IP stays (ADR-0009), so a replacement costs nothing extra.

## Decision

- Gateway user data (`live/hetzner/ovpn/openvpn/cloud-init.yaml.tftpl`) owns sysctl
  and the complete, static nftables rule set, including the rules for VPN
  clients. The rules match on addresses, not interface names, so they load at
  boot before `tun0` exists.
- Ansible (`live/hetzner/ovpn/ansible`, role `openvpn`) owns the OpenVPN package,
  server config, PKI and client configs.
- Ansible never writes nftables or sysctl. It only reads them and stops if
  forwarding or NAT is missing.

## Consequences

- The Gateway has NAT for the Private Hosts at boot, with no Ansible run.
- A new firewall rule goes in the template and replaces the Gateway. After the
  replacement, run `make configure` again.
- Terraform is the only source of the shared values (VPN network, port). Ansible
  reads them from the `ansible_inventory` output.
