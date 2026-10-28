# VOKO Narrowcasting - Yodeck Agenda Slide

Volledig geautomatiseerde narrowcasting slide voor VOKO digital signage op Yodeck schermen.

## Werking
1. **GitHub Actions:** Draait elke 6 uur `update_agenda.py` om de VOKO activiteitenpagina te scrapen.
2. **GitHub Pages:** Serveert `index.html` en de actuele `agenda.json` live via HTTPS.
3. **Yodeck:** Toont de webpagina op 1080p full-screen en ververst automatisch elke 15 minuten de DOM.
