#!/bin/bash
# ==============================================================================
# VOKO Narrowcasting - Automatische Agenda & Nieuws Updater Script
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [FOUT] Geen python3 gevonden!" >> update_agenda.log
    exit 1
fi

echo "========================================================" >> update_agenda.log
echo "$(date '+%Y-%m-%d %H:%M:%S') - Start update_agenda.py & update_nieuws.py" >> update_agenda.log

# 1. Update Agenda
"$PYTHON_BIN" "$SCRIPT_DIR/update_agenda.py" >> update_agenda.log 2>&1

# 2. Update Nieuws
if [ -f "$SCRIPT_DIR/update_nieuws.py" ]; then
    "$PYTHON_BIN" "$SCRIPT_DIR/update_nieuws.py" >> update_agenda.log 2>&1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Beide updates voltooid" >> update_agenda.log
