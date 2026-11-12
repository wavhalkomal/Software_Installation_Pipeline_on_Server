#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

swap_file="/swapfile"
if ! swapon --show=NAME --noheadings | grep -qx "${swap_file}"; then
  if [[ ! -f "${swap_file}" ]]; then
    fallocate -l 2G "${swap_file}" || dd if=/dev/zero of="${swap_file}" bs=1M count=2048
    chmod 600 "${swap_file}"
    mkswap "${swap_file}"
  fi
  swapon "${swap_file}"
fi

if ! grep -qF "${swap_file} none swap sw 0 0" /etc/fstab; then
  echo "${swap_file} none swap sw 0 0" >> /etc/fstab
fi

if ! rpm -q amazon-ssm-agent >/dev/null 2>&1; then
  dnf install -y "https://s3.amazonaws.com/ec2-downloads-windows/SSMAgent/latest/linux_amd64/amazon-ssm-agent.rpm"
fi

systemctl enable --now amazon-ssm-agent

echo "Bootstrap complete."
free -h
swapon --show
systemctl --no-pager --full status amazon-ssm-agent || true

