#!/usr/bin/env bash
# Generate a self-signed TLS cert for nginx (port 8443).
# Usage:  ./deploy/gen-cert.sh [hostname-or-ip]   (default: localhost)
set -euo pipefail

HOST="${1:-localhost}"
CERT_DIR="$(cd "$(dirname "$0")" && pwd)/nginx/certs"
mkdir -p "$CERT_DIR"

# SAN supports both a DNS name and a literal IP so browsers/curl accept it.
if [[ "$HOST" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  SAN="IP:${HOST}"
else
  SAN="DNS:${HOST}"
fi

openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$CERT_DIR/server.key" \
  -out    "$CERT_DIR/server.crt" \
  -days 825 \
  -subj "/C=MA/O=American School of Benguerir/CN=${HOST}" \
  -addext "subjectAltName=${SAN}"

echo "✓ Self-signed cert for '${HOST}' written to ${CERT_DIR}"
