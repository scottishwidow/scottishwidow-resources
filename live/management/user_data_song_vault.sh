#!/usr/bin/env bash
# Song Vault instance bootstrap.
# Updates the base system and installs Docker Engine from Docker's official
# apt repository, following https://docs.docker.com/engine/install/ubuntu/
#
# Runs once, as root, at first boot via EC2 user data. Editing this file does
# NOT re-run it on an existing instance — see user_data_replace_on_change in main.tf.

set -euxo pipefail

# Non-interactive apt: user data has no TTY, so any prompt would hang the boot.
export DEBIAN_FRONTEND=noninteractive

# --- Update base packages ---------------------------------------------------
apt-get update
apt-get upgrade -y

# --- Docker Engine: official apt repository ---------------------------------
# 1. Prerequisites and Docker's GPG key.
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

# 2. Add the repository. arch and codename are resolved on the host, so this is
#    correct on both amd64 and arm64 (Graviton) and across Ubuntu releases.
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
  | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update

# 3. Install the latest Docker Engine, CLI, containerd and the standard plugins.
apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

# 4. Ensure the daemon is enabled and running (systemd enables it by default,
#    but make it explicit so a reboot brings Docker back up).
systemctl enable --now docker

# 5. Let the default 'ubuntu' user run Docker without sudo. The group change
#    takes effect on their next login/session.
usermod -aG docker ubuntu
