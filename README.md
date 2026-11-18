# Sentinel War Radar — Mobile OSINT & Civil Alert PWA

> **Important Safety Notice:** Smartphones do **not** have physical RF radar hardware and cannot detect incoming missiles, drones, or aircraft in flight. This web application monitors public OSINT, breaking news, and civil alert feeds and triggers visual/audio notifications when matching reports appear within your Watch Zone. **Always rely on official government civil-defense sirens, Cell Broadcast alerts, and local authorities for life-safety.**

## Features
- **Tactical Radar Scope:** Mobile-first sweeping radar canvas showing reported threats by real compass bearing and distance from your Watch Location, with optional phone Compass Lock (`Heading-Up`), out-of-range rim markers, and tap-to-inspect telemetry.
- **Interactive Geo Map:** Dual-layer dark Slippy-Map tiles + offline vector continent fallback with watch-radius ring, touch pan/pinch-zoom, and category filters.
- **Live Multi-Source OSINT Aggregator:** Pulls live updates from Google News breaking attack feeds (global + dynamic local city watch), BBC, Al Jazeera, France 24, DW, The Guardian, GDELT 2.0 15-min Geo stream, GDACS UN/EC civil alerts, and USGS seismic sensors — plus custom user RSS feeds and multilingual watch keywords.
- **Proximity Audio & Drill Engine:** Synthesized Web Audio tones (`Air Raid Pulse`, `Tactical Sonar`, `Urgent Chime`), vibration, browser Push Notifications, Night Watch (Screen Wake Lock), and a safe `[SIMULATION DRILL]` test button.
- **Civil Defense Guide & 72-Hour Go-Bag Checklist:** Works offline via Service Worker PWA cache.

## Running on Your Phone or Self-Hosting
Zero third-party packages are required (pure Python 3 standard library):

```bash
cd /home/user/war-radar
python3 server.py
```

- **Local Wi-Fi / Hotspot:** Run `python3 server.py` on a computer or Android Termux, then open `http://<YOUR-LAN-IP>:8080` in Safari or Chrome on your phone (or use HTTPS reverse proxy / Cloudflare Tunnel for GPS & PWA install).
- **Install as App (PWA):** In Safari tap **Share → Add to Home Screen**; in Android Chrome tap **⋮ → Install App**.
