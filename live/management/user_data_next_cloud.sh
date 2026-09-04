#!/usr/bin/env bash
# Runs once, as root, at first boot via EC2 user data. Editing this file does NOT
# re-run it on an existing instance — see user_data_replace_on_change in main.tf.

set -euxo pipefail

# Non-interactive apt: user data has no TTY, so any prompt would hang the boot.
export DEBIAN_FRONTEND=noninteractive

# --- Update base packages ---------------------------------------------------
apt-get update
apt-get upgrade -y

# --- Docker Engine: official apt repository ---------------------------------
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# arch and codename are resolved on the host, so this is correct on amd64, arm64 and any Ubuntu release.
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update

apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

# Explicit --now so a reboot brings Docker back up, rather than relying on the default enable.
systemctl enable --now docker

# Lets 'ubuntu' run Docker without sudo; takes effect on their next login.
usermod -aG docker ubuntu
