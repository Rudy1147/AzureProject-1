#!/usr/bin/env bash
set -e

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y docker.io docker-compose-v2 docker-buildx git rsyslog
systemctl enable --now docker
systemctl enable --now rsyslog

rm -rf /home/azureuser/AzureProject-1
git clone https://github.com/Rudy1147/AzureProject-1.git /home/azureuser/AzureProject-1

cd /home/azureuser/AzureProject-1

docker compose up -d --build

docker compose ps

# This is to debug the containers if they are not running properly.
# You can check the logs of each service to see if there are any errors or issues that need to be addressed.
# This can be commented out in production, but it is useful for debugging during development and testing.
#docker compose logs auth
#docker compose logs api
#docker compose logs nginx

# This is to redirect the logs of each service to a separate log file in /var/log/AzureProject-1 directory.
docker logs -f api_service 2>&1 | logger -t api_service &
docker logs -f auth_service 2>&1 | logger -t auth_service &
docker logs -f load_balancer 2>&1 | logger -t nginx_service &

sleep 25
curl -I http://localhost:8081/logs || curl -I http://localhost:8081/

#Fix folder permissions
chown -R azureuser:azureuser /home/azureuser/AzureProject-1
