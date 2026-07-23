#!/usr/bin/env bash
set -e

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 docker-buildx git
systemctl enable --now docker

rm -rf /home/azureuser/AzureProject-1
git clone https://github.com/Rudy1147/AzureProject-1.git /home/azureuser/AzureProject-1

cd /home/azureuser/AzureProject-1
# This is to ensure that the logs directory exists before starting the containers.
mkdir -p /var/log/AzureProject-1

docker compose up -d --build

docker compose ps

# This is to debug the containers if they are not running properly.
# You can check the logs of each service to see if there are any errors or issues that need to be addressed.
# This can be commented out in production, but it is useful for debugging during development and testing.
docker compose logs auth
docker compose logs api
docker compose logs nginx

# This is to redirect the logs of each service to a separate log file in /var/log/AzureProject-1 directory.
docker logs -f api_service >> /var/log/AzureProject-1/api.log 2>&1 &
docker logs -f auth_service >> /var/log/AzureProject-1/auth.log 2>&1 &
docker logs -f load_balancer >> /var/log/AzureProject-1/nginx.log 2>&1 &

sleep 25
curl -I http://localhost:8081/logs || curl -I http://localhost:8081/

#Fix folder permissions
chown -R azureuser:azureuser /home/azureuser/AzureProject-1
