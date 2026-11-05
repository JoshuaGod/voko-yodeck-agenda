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

## Werking & Architectuur
1. **GitHub Actions:** Draait elke 6 uur `update_agenda.py` om de VOKO activiteitenpagina te scrapen.
2. **GitHub Pages:** Serveert alle HTML-slides en assets direct en snel via HTTPS.
3. **Yodeck Narrowcasting:** Speelt de URL's op 1080p full-screen af via de Yodeck mediaplayer en ververst periodiek de pagina's in het geheugen.
