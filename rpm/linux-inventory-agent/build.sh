#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
image_name="linux-inventory-agent-builder:1.0.0"
container_name="linux-inventory-agent-export"

mkdir -p "${project_dir}/dist"
docker build --platform linux/amd64 -t "${image_name}" -f "${project_dir}/Dockerfile.build" "${project_dir}"
docker rm -f "${container_name}" >/dev/null 2>&1 || true
docker create --name "${container_name}" "${image_name}" >/dev/null
docker cp "${container_name}:/root/rpmbuild/RPMS/noarch/." "${project_dir}/dist/"
docker rm "${container_name}" >/dev/null

rpm_file="$(find "${project_dir}/dist" -name 'linux-inventory-agent-*.rpm' -type f | head -n 1)"
if [[ -z "${rpm_file}" ]]; then
  echo "RPM build failed: output file not found" >&2
  exit 1
fi

echo "Built: ${rpm_file}"
shasum -a 256 "${rpm_file}"

