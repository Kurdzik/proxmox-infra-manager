#!/bin/bash
# Official Docker CE installation for RHEL-compatible distros
# (Rocky Linux, AlmaLinux, Fedora, CentOS Stream)
# Source: https://docs.docker.com/engine/install/rhel/
set -euo pipefail

. /etc/os-release

dnf install -y -q dnf-plugins-core

if [ "$ID" = "fedora" ]; then
    REPO_URL="https://download.docker.com/linux/fedora/docker-ce.repo"
else
    REPO_URL="https://download.docker.com/linux/rhel/docker-ce.repo"
fi

dnf config-manager --add-repo "$REPO_URL"
dnf install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker
systemctl start docker
