#!/bin/bash
# ==============================================================================
# VOKO Narrowcasting - Automatische Agenda Updater Script
# ==============================================================================

# Zorg dat we altijd in de juiste map werken
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# Bepaal Python interpreter (/usr/local/bin/python3 of python3 in PATH)
if [ -x "/usr/local/bin/python3" ]; then
    PYTHON_BIN="/usr/local/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [FOUT] Geen python3 gevonden!" >> update_agenda.log
    exit 1
fi

echo "========================================================" >> update_agenda.log
echo "$(date '+%Y-%m-%d %H:%M:%S') - Start update_agenda.py" >> update_agenda.log
"$PYTHON_BIN" "$SCRIPT_DIR/update_agenda.py" >> update_agenda.log 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Succesvol bijgewerkt (exit code: $EXIT_CODE)" >> update_agenda.log
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [FOUT] Scraper mislukt met exit code: $EXIT_CODE" >> update_agenda.log
fi

exit $EXIT_CODE
