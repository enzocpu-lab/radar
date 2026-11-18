import json
import math
import mimetypes
import os
import sys
import time
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
sys.path.insert(0, str(BASE_DIR))

from feeds import gather_all_feeds
from gazetteer import haversine_km, initial_bearing_deg, search_gazetteer

mimetypes.add_type("application/manifest+json", ".webmanifest")
mimetypes.add_type("image/svg+xml", ".svg")


def _nominatim_search(query: str) -> list:
    try:
        url = (
            "https://nominatim.openstreetmap.org/search?format=json&limit=5&q="
            + urllib.parse.quote_plus(query)
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SentinelWarRadarOSINT/1.0 (+mobile-pwa)"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            rows = json.loads(resp.read().decode("utf-8", errors="replace"))
        out = []
        for r in rows:
            out.append({
                "name": (r.get("display_name") or query).split(",")[0:2],
                "fullName": r.get("display_name") or query,
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "kind": r.get("type") or "place",
                "country": "",
            })
        for item in out:
            if isinstance(item["name"], list):
                item["name"] = ", ".join(s.strip() for s in item["name"] if s.strip())
        return out
    except Exception:
        return []


class RadarHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        # Clean concise server log
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} - {format % args}\n")
        sys.stdout.flush()

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/health":
            return self._send_json(200, {"status": "ok", "timestamp": int(time.time())})

        if path == "/api/feed":
            qs = urllib.parse.parse_qs(parsed.query)
            watch = (qs.get("watch") or [""])[0]
            kw_raw = (qs.get("kw") or [""])[0]
            feeds_raw = (qs.get("feeds") or [""])[0]
            lat_s = (qs.get("lat") or [""])[0]
            lon_s = (qs.get("lon") or [""])[0]
            return self._handle_feed(watch, kw_raw, feeds_raw, lat_s, lon_s)

        if path == "/api/geocode":
            qs = urllib.parse.parse_qs(parsed.query)
            q = (qs.get("q") or [""])[0].strip()
            local = search_gazetteer(q, limit=8)
            if len(local) < 3 and len(q) >= 3:
                remote = _nominatim_search(q)
                seen_names = {r["name"].lower() for r in local}
                for item in remote:
                    if item["name"].lower() not in seen_names:
                        local.append(item)
                        seen_names.add(item["name"].lower())
            return self._send_json(200, {"results": local[:10]})

        return self._serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/api/feed":
            return self._send_json(404, {"error": "Not found"})
        try:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(min(length, 65536)).decode("utf-8", errors="replace")
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {}
        kw_raw = body.get("keywords")
        feeds_raw = body.get("customFeeds")
        return self._handle_feed(
            watch=str(body.get("watch") or ""),
            kw_list=[str(x) for x in kw_raw] if isinstance(kw_raw, list) else [],
            feed_list=[str(x) for x in feeds_raw] if isinstance(feeds_raw, list) else [],
            lat_s=body.get("lat"),
            lon_s=body.get("lon"),
        )

    def _handle_feed(self, watch="", kw_raw="", feeds_raw="", lat_s="", lon_s="", kw_list=None, feed_list=None):
        if kw_list is None:
            kw_list = [k.strip() for k in kw_raw.split(",") if k.strip()] if kw_raw else []
        if feed_list is None:
            feed_list = [u.strip() for u in feeds_raw.split("|") if u.strip()] if feeds_raw else []

        data = gather_all_feeds(
            watch_query=watch,
            custom_keywords=kw_list,
            custom_feed_urls=feed_list,
        )

        # Optionally compute distance/bearing relative to user coordinates
        user_lat = user_lon = None
        try:
            if lat_s not in ("", None) and lon_s not in ("", None):
                la = float(lat_s)
                lo = float(lon_s)
                if math.isfinite(la) and math.isfinite(lo) and -90 <= la <= 90 and -180 <= lo <= 180:
                    user_lat, user_lon = la, lo
        except (ValueError, TypeError):
            user_lat = user_lon = None

        events_out = []
        for ev in data["events"]:
            item = dict(ev)
            if user_lat is not None and user_lon is not None and item.get("lat") is not None and item.get("lon") is not None:
                item["distanceKm"] = round(haversine_km(user_lat, user_lon, item["lat"], item["lon"]), 1)
                item["bearingDeg"] = round(initial_bearing_deg(user_lat, user_lon, item["lat"], item["lon"]), 1)
            else:
                item["distanceKm"] = None
                item["bearingDeg"] = None
            events_out.append(item)

        payload = dict(data)
        payload["events"] = events_out
        return self._send_json(200, payload)

    def _serve_static(self, req_path: str):
        clean_path = urllib.parse.unquote(req_path).lstrip("/")
        if not clean_path or clean_path == "":
            clean_path = "index.html"
        target = (PUBLIC_DIR / clean_path).resolve()
        if not str(target).startswith(str(PUBLIC_DIR.resolve())) or not target.is_file():
            # Fallback to index.html for SPA routes, 404 for missing assets with extension
            if "." in clean_path:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            target = PUBLIC_DIR / "index.html"

        data = target.read_bytes()
        ctype, _ = mimetypes.guess_type(str(target))
        if not ctype:
            ctype = "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript", "application/json", "application/manifest+json"):
            ctype = f"{ctype}; charset=utf-8"

        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if target.name == "sw.js":
            self.send_header("Service-Worker-Allowed", "/")
            self.send_header("Cache-Control", "no-cache")
        elif target.name == "index.html":
            self.send_header("Cache-Control", "no-cache")
        else:
            self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        self.wfile.write(data)


def main():
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), RadarHandler)
    print(f"Sentinel War Radar PWA listening on http://0.0.0.0:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
