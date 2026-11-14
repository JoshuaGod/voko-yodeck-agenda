#!/bin/bash
# ==============================================================================
# VOKO Narrowcasting - Veilig synchroniseren & pushen naar GitHub
# Haalt eerst automatisch de nieuwste scraper-data op en pusht daarna.
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔄 Ophalen van eventuele automatische scraper-updates op GitHub..."
git pull --rebase

echo "🚀 Pushen van jouw lokale wijzigingen naar GitHub Pages..."
git push

echo "✅ Alles staat live op GitHub Pages!"
