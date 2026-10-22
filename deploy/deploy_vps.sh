#!/usr/bin/env bash
# Script de déploiement automatique en 1 commande sur votre VPS (Ubuntu / Debian)
set -e

echo "=== [Nexus Pulse] Préparation et déploiement sur VPS ==="

if ! command -v docker &> /dev/null; then
    echo "[*] Installation de Docker..."
    curl -fsSL https://get.docker.com | sh
fi

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "[+] Fichier .env initialisé depuis .env.example"
fi

echo "[*] Lancement des conteneurs de production (FastAPI + Caddy Reverse Proxy)..."
docker compose -f deploy/docker-compose.yml up -d --build

echo "=== [SUCCÈS] Votre entreprise en ligne Nexus Pulse tourne en continu sur le port 80 / 8000 ! ==="
