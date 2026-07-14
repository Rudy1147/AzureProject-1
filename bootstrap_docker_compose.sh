#!/usr/bin/env bash
set -e

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 docker-buildx git
systemctl enable --now docker

rm -rf /home/azureuser/AzureProject-0
git clone https://github.com/Rudy1147/AzureProject-1.git /home/azureuser/AzureProject-1

cd /home/azureuser/AzureProject-1

docker compose up -d --build

docker compose ps
sleep 5
curl -I http://localhost:8081/health || curl -I http://localhost:8081/

#Fix folder permissions
chown -R azureuser:azureuser /home/azureuser/AzureProject-1