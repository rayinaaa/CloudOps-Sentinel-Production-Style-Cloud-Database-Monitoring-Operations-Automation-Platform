#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Local Development Onboarding & Bootstrap Script
# ==============================================================================

set -euo pipefail

echo "======================================================================"
echo " CloudOps Sentinel - Bootstrap Local Development Environment"
echo "======================================================================"

# 1. Environment file initialization
if [ ! -f .env ]; then
    echo "[+] Creating .env from .env.example..."
    cp .env.example .env
    echo "[!] .env created. Review credentials and tuning parameters if needed."
else
    echo "[*] Existing .env file detected. Skipping overwrite."
fi

# 2. Check Docker daemon
if ! docker info > /dev/null 2>&1; then
    echo "[-] Error: Docker daemon is not running. Please start Docker and retry."
    exit 1
fi

# 3. Spin up services in background
echo "[+] Starting PostgreSQL databases and observability telemetry stack..."
docker compose up -d sentinel-db monitored-db prometheus grafana

echo "[+] Waiting for sentinel-db to report healthy status..."
until [ "`docker inspect -f {{.State.Health.Status}} sentinel-postgres 2>/dev/null`"=="healthy" ]; do
    sleep 2
    printf "."
done
echo ""
echo "[+] sentinel-db is ready!"

# 4. Run database migrations
echo "[+] Running Alembic migrations inside virtualenv or container..."
if command -v alembic > /dev/null 2>&1; then
    cd backend && alembic upgrade head && cd ..
else
    echo "[*] Local alembic CLI not detected. Run migrations via Docker container:"
    echo "    docker compose run --rm backend alembic upgrade head"
fi

echo "======================================================================"
echo " CloudOps Sentinel Environment is Ready!"
echo "   - Sentinel API:       http://localhost:8000"
echo "   - API Docs (Swagger): http://localhost:8000/docs"
echo "   - Health Check:       http://localhost:8000/api/v1/health/ready"
echo "   - Prometheus:         http://localhost:9090"
echo "   - Grafana:            http://localhost:3001 (admin/admin)"
echo "   - Monitored Target:   localhost:5433 (ecommerce_production)"
echo "======================================================================"

