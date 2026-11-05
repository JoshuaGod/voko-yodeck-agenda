# VOKO Narrowcasting - Yodeck Kantine Schermen

Volledig geautomatiseerde narrowcasting slides voor VOKO digital signage op Yodeck schermen in de sportkantine.

## Live Schermen & URL's (GitHub Pages)

### Sponsoren (Nieuw: Billboard Stijl 1080p)
De sponsor uitingen zijn ontworpen in de rustige, professionele VOKO kantine-huisstijl (donkergrijze topbalk, rode wave-banner en Barlow typografie) gecombineerd met de unieke merkidentiteit van elke sponsor:

- 🔄 **Alle Sponsoren Carrousel (Aanrader voor Yodeck):**  
  [`https://joshuagod.github.io/voko-yodeck-agenda/sponsoren.html`](https://joshuagod.github.io/voko-yodeck-agenda/sponsoren.html)  
  *Roteert automatisch elke 12 seconden tussen de sponsoren met een soepele fade en voortgangsbalk.*
- 🛋️ **PC Interieur:**  
  [`https://joshuagod.github.io/voko-yodeck-agenda/sponsor-pcinterieur.html`](https://joshuagod.github.io/voko-yodeck-agenda/sponsor-pcinterieur.html)  
  *Gordijnen, raambekleding, vloeren en showroom Bredaseweg 23.*
- ⚡ **Topical (voorheen Notulensoftware):**  
  [`https://joshuagod.github.io/voko-yodeck-agenda/sponsor-topical.html`](https://joshuagod.github.io/voko-yodeck-agenda/sponsor-topical.html)  
  *AI-notulen en actielijsten in 1 minuut voor teams en besturen.*
- 🔨 **JorB Projecten:**  
  [`https://joshuagod.github.io/voko-yodeck-agenda/sponsor-jorb.html`](https://joshuagod.github.io/voko-yodeck-agenda/sponsor-jorb.html)  
  *Allround vakmanschap door clubgenoot Joris Blankestijn (bouw, tuinen, renovatie).*

### Club & Wedstrijd Schermen
- 📅 **Agenda:** [`https://joshuagod.github.io/voko-yodeck-agenda/index.html`](https://joshuagod.github.io/voko-yodeck-agenda/index.html)
- 📰 **Nieuws:** [`https://joshuagod.github.io/voko-yodeck-agenda/nieuws.html`](https://joshuagod.github.io/voko-yodeck-agenda/nieuws.html)
- 🏐 **Programma:** [`https://joshuagod.github.io/voko-yodeck-agenda/programma.html`](https://joshuagod.github.io/voko-yodeck-agenda/programma.html)
- 🏆 **Standen:** [`https://joshuagod.github.io/voko-yodeck-agenda/standen.html`](https://joshuagod.github.io/voko-yodeck-agenda/standen.html)
- 📊 **Uitslagen:** [`https://joshuagod.github.io/voko-yodeck-agenda/uitslagen.html`](https://joshuagod.github.io/voko-yodeck-agenda/uitslagen.html)
- 📸 **Oproep Teamfoto's:** [`https://joshuagod.github.io/voko-yodeck-agenda/oproep-teamfoto.html`](https://joshuagod.github.io/voko-yodeck-agenda/oproep-teamfoto.html)
- 🥇 **Team van het Jaar:** [`https://joshuagod.github.io/voko-yodeck-agenda/team-van-het-jaar.html`](https://joshuagod.github.io/voko-yodeck-agenda/team-van-het-jaar.html)  
  *Tussenstand Team van het Jaar op basis van vrijwilligerspunten per team.*

## Werking & Architectuur
1. **GitHub Actions:** Draait elke 6 uur `update_agenda.py` om de VOKO activiteitenpagina te scrapen.
2. **GitHub Pages:** Serveert alle HTML-slides en assets direct en snel via HTTPS.
3. **Yodeck Narrowcasting:** Speelt de URL's op 1080p full-screen af via de Yodeck mediaplayer en ververst periodiek de pagina's in het geheugen.

## Team van het Jaar (`team-van-het-jaar.html` & `.json`)
- **Doel:** Toont de actuele tussenstand van de teamcompetitie voor vrijwilligersinzet op de kantine-tv.
- **Gegevensbron:** Wordt gevoed door `team-van-het-jaar.json`. Deze data wordt gegenereerd vanuit het lokale vrijwilligersdashboard (`voko-vrijstellingspunten`) en handmatig gecommit/gepusht bij puntenupdates.
- **Privacy (AVG):** Bevat **uitsluitend geaggregeerde teamtotalen** (geen lidnamen, e-mailadressen, Club-Assistent URL's of individuele pilot-vergoedingen).
- **Rekenregels teamdoelen:**
  - Standaard teamdoel: 18 punten per spelend lid.
  - Uitzonderingen: MC1 (12 pt p.p.), MC2 (12 pt p.p.), Dames 3 (13 pt p.p.) en Volley Stars (12 pt p.p.).
  - Overvloei van punten (bijv. overschot van een team dat doorgeschoven wordt naar een ander team) wordt netjes verwerkt in `beh` en `delta`.

## Changelog & Recente Updates
- **2026-11-05 (Sponsor Billboard Uitingen & Carrousel):**
  - Nieuwe rustige narrowcasting slides toegevoegd in de officiële VOKO TV-kantine huisstijl voor:
    - **PC Interieur** (`sponsor-pcinterieur.html`)
    - **Topical** (`sponsor-topical.html`)
    - **JorB Projecten** (`sponsor-jorb.html`)
  - Auto-roterende carrousel slide toegevoegd (`sponsoren.html`) met 12-seconden crossfade en voortgangsbalk voor eenvoudige weergave op Yodeck.
  - Alle assets en vector QR-codes ondergebracht in `assets/sponsoren/`.
  - Hoge resolutie 1080p vector PDF's en PNG's gegenereerd voor print/archief.
