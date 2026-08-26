#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y wireguard iptables
sudo install -d -m 700 /etc/wireguard
echo 'Generate /etc/wireguard/server.key out-of-band with umask 077.'
echo 'Configure wg0.conf with the node public address, then enable net.ipv4.ip_forward and NAT.'
sudo systemctl enable wg-quick@wg0
