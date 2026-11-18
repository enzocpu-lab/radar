import csv
import email.utils
import hashlib
import io
import ipaddress
import json
import re
import socket
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

from gazetteer import geolocate_text

USER_AGENT = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"

STATIC_RSS_FEEDS = [
    ("Google News · Attack Alerts", "https://news.google.com/rss/search?q=(airstrike+OR+%22missile+attack%22+OR+%22drone+attack%22+OR+%22air+raid%22+OR+shelling+OR+bombardment+OR+%22rocket+attack%22)+when:1d&hl=en-US&gl=US&ceid=US:en", "osint"),
    ("BBC · Middle East", "https://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "news"),
    ("BBC · Europe", "https://feeds.bbci.co.uk/news/world/europe/rss.xml", "news"),
    ("BBC · World", "https://feeds.bbci.co.uk/news/world/rss.xml", "news"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "news"),
    ("France 24", "https://www.france24.com/en/rss", "news"),
    ("DW · World", "https://rss.dw.com/xml/rss-en-world", "news"),
    ("The Guardian · World", "https://www.theguardian.com/world/rss", "news"),
]

CRITICAL_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bair\s*strikes?\b",
        r"\bair\s*raids?\b",
        r"\bmissile\s*(attack|strike|barrage|launch|fired|hit|hits|intercept)",
        r"\bmissiles?\s*(?:!|at\b|hit\b|strike\b|target)",
        r"\bballistic\s*missile",
        r"\bcruise\s*missile",
        r"\bdrone\s*(attack|strike|swarm|barrage|intercept|thwart|kills?)",
        r"\bsea\s*drone\s*(attack|strike)",
        r"\brocket\s*(attack|fire|barrage|strike)",
        r"\bshelling\b",
        r"\bbombardment\b",
        r"\bsirens?\s*(sound|blare|wail|warning|alert)",
        r"\bred\s*alert\b",
        r"\bdouble[- ]tap\s*strike\b",
        r"\bevacuation\s*order",
        r"\bheavy\s*explosions?\b",
        r"\bstrikes?\s*(kills?|hits?|targets?|damage|collapses?)\b",
        r"\battack\s*on\b",
        r"\bthwarts\s*drone\b",
        r"\btargets\s*(us\s*radar|air\s*base|bridge|facility)\b",
    ]
]

HIGH_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bmissiles?\b",
        r"\bdrones?\b",
        r"\bair\s*defen[cs]es?\b",
        r"\banti[- ]aircraft\b",
        r"\bexplosions?\b",
        r"\bblast\b",
        r"\bartillery\b",
        r"\bclashes\b",
        r"\bgunfire\b",
        r"\bstrikes?\b",
        r"\battack(s|ed|ing)?\b",
        r"\braids?\b",
        r"\binvasion\b",
        r"\bintercept(ed|ion|s)?\b",
        r"\bfighter\s*jets?\b",
        r"\bwarships?\b",
        r"\baircraft\s*carrier\b",
        r"\brebel\s*advance\b",
        r"\bforces\s*retreat\b",
        r"\bshot\s*dead\b",
    ]
]

MODERATE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bmilitary\b",
        r"\btroops\b",
        r"\bconflict\b",
        r"\bwar\b",
        r"\bcombat\b",
        r"\bceasefire\b",
        r"\bescalat(e|es|ion)\b",
        r"\bretaliat(e|ion)\b",
        r"\bsecurity\s*alert\b",
        r"\bfrontline\b",
        r"\bnuclear\b",
        r"\bhouthi\b",
        r"\bhezbollah\b",
    ]
]

NOISE_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\bheart\s*attack\b",
        r"\bpanic\s*attack\b",
        r"\bshark\s*attack\b",
        r"\basthma\s*attack\b",
        r"\bdog\s*attack\b",
        r"\bsentenced\s+to\b",
        r"\bjailed\b",
        r"\bprison\b",
        r"\bmurder\s*trial\b",
        r"\bworld\s*war\s*(i|ii|1|2)\b",
        r"\bwwii\b",
        r"\bvideo\s*game\b",
        r"\bnetflix\b",
        r"\bbox\s*office\b",
        r"\bpremier\s*league\b",
        r"\bchampions\s*league\b",
        r"\bfashion\b",
        r"\brecipe\b",
        r"\bstock\s*market\b",
        r"\bnvidia\b",
        r"\bepstein\b",
        r"\beducation\s*protests\b",
        r"\bcultivated\s*chicken\b",
        r"\bhome\s*invasion\b",
        r"\bgas\s*station\b",
        r"\borchestra\b",
        r"\binquest\b",
    ]
]

GDELT_MIL_TITLE_RE = re.compile(
    r"\b(missile|drone|airstrike|air\s*strike|air\s*raid|shelling|bombard|artillery|rocket|war|military|ukraine|russia|iran|israel|gaza|lebanon|yemen|sudan|bahrain|hormuz|crimea|air\s*defen[cs]e|siren)\b",
    re.IGNORECASE,
)

# Simple in-memory caches
_CACHE: Dict[str, Tuple[float, Any]] = {}
_CACHE_TTL_BASE = 45.0
_CACHE_TTL_GDELT = 180.0


def _strip_html(raw: str) -> str:
    txt = unescape(raw or "")
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def _parse_pubdate(raw: str) -> int:
    if not raw:
        return int(time.time())
    s = raw.strip()
    try:
        dt = email.utils.parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        pass
    try:
        iso = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except Exception:
        return int(time.time())


def _is_safe_public_url(url: str) -> bool:
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme not in ("http", "https") or not p.hostname:
            return False
        host = p.hostname.lower()
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1") or host.endswith(".local"):
            return False
        infos = socket.getaddrinfo(host, None)
        for info in infos:
            ip_str = info[4][0]
            ip = ipaddress.ip_address(ip_str)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        return True
    except Exception:
        return False


def _fetch_bytes(url: str, timeout: int = 10, max_bytes: int = 3_000_000) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(max_bytes)


def classify_text(title: str, summary: str = "", custom_keywords: Optional[List[str]] = None) -> Tuple[Optional[str], List[str], bool]:
    title_str = (title or "").strip()
    combined = f"{title_str} {summary}".strip()

    if any(p.search(combined) for p in NOISE_PATTERNS):
        if not any(p.search(title_str) for p in CRITICAL_PATTERNS):
            return None, [], False

    matched_tags: List[str] = []
    custom_hit = False

    if custom_keywords:
        low = combined.lower()
        for kw in custom_keywords:
            k = kw.strip().lower()
            if len(k) >= 2 and k in low:
                matched_tags.append(f"kw:{kw.strip()}")
                custom_hit = True

    if custom_hit:
        return "critical", matched_tags[:4], True

    # Classify strictly against title first so investigative prose in description doesn't cause false positives
    for pat in CRITICAL_PATTERNS:
        m = pat.search(title_str)
        if m:
            matched_tags.append(m.group(0).strip())
            if len(matched_tags) >= 3:
                break
    if matched_tags:
        return "critical", matched_tags, False

    for pat in HIGH_PATTERNS:
        m = pat.search(title_str)
        if m:
            matched_tags.append(m.group(0).strip())
            if len(matched_tags) >= 3:
                break
    if matched_tags:
        return "high", matched_tags, False

    for pat in MODERATE_PATTERNS:
        m = pat.search(title_str)
        if m:
            matched_tags.append(m.group(0).strip())
            if len(matched_tags) >= 2:
                break
    if matched_tags:
        return "moderate", matched_tags, False

    return None, [], False


def _clean_google_news_title(title: str) -> Tuple[str, Optional[str]]:
    if " - " in title:
        parts = title.rsplit(" - ", 1)
        if len(parts[1]) <= 40:
            return parts[0].strip(), parts[1].strip()
    return title, None


def _parse_rss_or_atom(xml_bytes: bytes, source_name: str, category: str, custom_keywords: Optional[List[str]] = None, force_include: bool = False) -> List[Dict[str, Any]]:
    items_out: List[Dict[str, Any]] = []
    root = ET.fromstring(xml_bytes)

    rss_items = root.findall(".//item")
    atom_ns = "{http://www.w3.org/2005/Atom}"
    atom_entries = root.findall(f".//{atom_ns}entry") if not rss_items else []

    raw_records: List[Tuple[str, str, str, str]] = []
    for it in rss_items[:35]:
        t = _strip_html(it.findtext("title") or "")
        desc = _strip_html(it.findtext("description") or "")
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date") or "").strip()
        raw_records.append((t, desc, link, pub))

    for en in atom_entries[:35]:
        t = _strip_html(en.findtext(f"{atom_ns}title") or "")
        desc = _strip_html(en.findtext(f"{atom_ns}summary") or en.findtext(f"{atom_ns}content") or "")
        link_el = en.find(f"{atom_ns}link")
        link = (link_el.attrib.get("href", "") if link_el is not None else "").strip()
        pub = (en.findtext(f"{atom_ns}updated") or en.findtext(f"{atom_ns}published") or "").strip()
        raw_records.append((t, desc, link, pub))

    for raw_title, desc, link, pub in raw_records:
        if not raw_title:
            continue
        title = raw_title
        sub_source = None
        if source_name.startswith("Google News"):
            title, sub_source = _clean_google_news_title(raw_title)

        severity, tags, is_custom = classify_text(title, desc, custom_keywords)
        if not severity:
            if force_include:
                severity = "info"
                tags = ["custom-feed"]
            else:
                continue

        geo = geolocate_text(title) or geolocate_text(desc)
        ts = _parse_pubdate(pub)
        uid_seed = f"{title.lower()[:80]}|{link[:80]}"
        eid = "ev_" + hashlib.sha1(uid_seed.encode("utf-8", errors="ignore")).hexdigest()[:14]

        items_out.append({
            "id": eid,
            "title": title,
            "summary": desc[:240] if desc and desc.lower() != title.lower() else "",
            "url": link,
            "source": sub_source or source_name,
            "feedGroup": source_name,
            "category": category if not is_custom else "custom",
            "severity": severity,
            "tags": tags,
            "timestamp": ts,
            "lat": geo["lat"] if geo else None,
            "lon": geo["lon"] if geo else None,
            "locationName": geo["locationName"] if geo else "Global / Unlocated",
            "geoPrecision": geo["geoPrecision"] if geo else "none",
            "country": geo["country"] if geo else "",
            "isSimulated": False,
        })
    return items_out


def _humanize_url_slug(url: str) -> str:
    try:
        path = urllib.parse.urlparse(url).path.strip("/")
        if not path:
            return ""
        seg = [s for s in path.split("/") if len(s) > 10 and not s.isdigit()]
        if not seg:
            return ""
        slug = seg[-1]
        slug = re.sub(r"\.(html?|php|aspx?|cms)$", "", slug, flags=re.IGNORECASE)
        slug = re.sub(r"-[a-f0-9]{6,}$", "", slug)
        slug = re.sub(r"-\d{5,}$", "", slug)
        slug = re.sub(r"^\d+[-.]", "", slug)
        words = slug.replace("-", " ").replace("_", " ").strip()
        alpha_words = [w for w in words.split() if re.search(r"[a-zA-Z]{2,}", w)]
        if len(alpha_words) < 4:
            return ""
        clean = " ".join(words.split())
        return clean[:1].upper() + clean[1:]
    except Exception:
        return ""


def _fetch_gdelt_live(custom_keywords: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    now = time.time()
    cached = _CACHE.get("gdelt_live_v2")
    if cached and (now - cached[0]) < _CACHE_TTL_GDELT and not custom_keywords:
        return cached[1]

    last_txt = _fetch_bytes("https://data.gdeltproject.org/gdeltv2/lastupdate.txt", timeout=10).decode("utf-8", errors="replace")
    export_url = None
    for line in last_txt.splitlines():
        parts = line.strip().split()
        if len(parts) >= 3 and parts[2].endswith(".export.CSV.zip"):
            export_url = parts[2]
            break
    if not export_url:
        return []

    zbytes = _fetch_bytes(export_url, timeout=15)
    events: List[Dict[str, Any]] = []
    seen_urls = set()

    with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
        fname = zf.namelist()[0]
        reader = csv.reader(io.TextIOWrapper(zf.open(fname), encoding="utf-8", errors="replace"), delimiter="\t")
        for row in reader:
            if len(row) < 61:
                continue
            event_code = row[26]
            root_code = row[28]
            if root_code not in ("18", "19", "20"):
                continue
            lat_s, lon_s = row[56], row[57]
            if not lat_s or not lon_s:
                continue
            url = row[60].strip()
            if not url or url in seen_urls:
                continue

            slug_title = _humanize_url_slug(url)
            if not slug_title:
                continue
            if not GDELT_MIL_TITLE_RE.search(slug_title):
                continue

            severity, tags, is_custom = classify_text(slug_title, "", custom_keywords)
            if not severity or severity == "moderate":
                continue

            seen_urls.add(url)
            # Prefer text-matched target geo if GDELT geo is publisher location; otherwise use exact GDELT coords
            text_geo = geolocate_text(slug_title)
            try:
                lat = text_geo["lat"] if text_geo else float(lat_s)
                lon = text_geo["lon"] if text_geo else float(lon_s)
                loc_name = text_geo["locationName"] if text_geo else (row[52] or row[53] or "Conflict Zone").strip()
                geo_prec = text_geo["geoPrecision"] if text_geo else "exact"
            except ValueError:
                continue

            date_str = row[59]
            try:
                dt = datetime.strptime(date_str[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                ts = int(dt.timestamp())
            except Exception:
                ts = int(now)

            host = (urllib.parse.urlparse(url).hostname or "gdelt").replace("www.", "")
            eid = "gd_" + hashlib.sha1(url.encode("utf-8", errors="ignore")).hexdigest()[:14]

            events.append({
                "id": eid,
                "title": slug_title,
                "summary": f"GDELT 2.0 Event (CAMEO {event_code}) · {loc_name}",
                "url": url,
                "source": f"GDELT · {host}",
                "feedGroup": "GDELT 2.0 Live Stream",
                "category": "osint" if not is_custom else "custom",
                "severity": severity,
                "tags": tags or [f"CAMEO-{event_code}"],
                "timestamp": ts,
                "lat": lat,
                "lon": lon,
                "locationName": loc_name,
                "geoPrecision": geo_prec,
                "country": (text_geo["country"] if text_geo else row[53]) or "",
                "isSimulated": False,
            })
            if len(events) >= 25:
                break

    if not custom_keywords:
        _CACHE["gdelt_live_v2"] = (now, events)
    return events


def _fetch_gdacs() -> List[Dict[str, Any]]:
    raw = _fetch_bytes("https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?alertlevel=Green;Orange;Red&limit=15", timeout=10)
    data = json.loads(raw.decode("utf-8", errors="replace"))
    out: List[Dict[str, Any]] = []
    for feat in data.get("features", [])[:15]:
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        props = feat.get("properties") or {}
        if len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        alert_lvl = (props.get("alertlevel") or "Green").lower()
        sev = "high" if alert_lvl == "red" else "disaster" if alert_lvl == "orange" else "info"
        title = props.get("name") or props.get("description") or "GDACS Civil Alert"
        ts = _parse_pubdate(props.get("fromdate") or "")
        url = (props.get("url") or {}).get("report") or "https://www.gdacs.org/"
        eid = f"gdacs_{props.get('eventtype', 'EV')}_{props.get('eventid', '')}"
        out.append({
            "id": eid,
            "title": f"[{alert_lvl.upper()}] {title}",
            "summary": _strip_html(props.get("htmldescription") or props.get("description") or ""),
            "url": url,
            "source": "GDACS · UN/EC",
            "feedGroup": "GDACS Civil Alerts",
            "category": "disaster",
            "severity": sev,
            "tags": [props.get("eventtype") or "Civil Alert", alert_lvl.upper()],
            "timestamp": ts,
            "lat": lat,
            "lon": lon,
            "locationName": props.get("country") or title,
            "geoPrecision": "exact",
            "country": props.get("country") or "",
            "isSimulated": False,
        })
    return out


def _fetch_usgs() -> List[Dict[str, Any]]:
    raw = _fetch_bytes("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson", timeout=10)
    data = json.loads(raw.decode("utf-8", errors="replace"))
    out: List[Dict[str, Any]] = []
    for feat in data.get("features", [])[:18]:
        coords = (feat.get("geometry") or {}).get("coordinates") or []
        props = feat.get("properties") or {}
        if len(coords) < 2:
            continue
        lon, lat = float(coords[0]), float(coords[1])
        mag = float(props.get("mag") or 0)
        sev = "disaster" if mag >= 5.2 else "info"
        ts = int((props.get("time") or time.time() * 1000) / 1000)
        title = props.get("title") or f"M {mag:.1f} Earthquake"
        place = props.get("place") or "Seismic Event"
        out.append({
            "id": "usgs_" + str(feat.get("id") or hashlib.sha1(title.encode()).hexdigest()[:10]),
            "title": title,
            "summary": f"Depth {coords[2]:.1f} km · USGS Seismic Network" if len(coords) > 2 else "USGS Seismic Network",
            "url": props.get("url") or "https://earthquake.usgs.gov/",
            "source": "USGS Seismic",
            "feedGroup": "USGS Earthquakes",
            "category": "disaster",
            "severity": sev,
            "tags": [f"M{mag:.1f}"],
            "timestamp": ts,
            "lat": lat,
            "lon": lon,
            "locationName": place,
            "geoPrecision": "exact",
            "country": "",
            "isSimulated": False,
        })
    return out


def _deduplicate(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sev_rank = {"critical": 4, "high": 3, "disaster": 2, "moderate": 1, "info": 0}
    events.sort(key=lambda e: (e["timestamp"], sev_rank.get(e["severity"], 0)), reverse=True)

    kept: List[Dict[str, Any]] = []
    seen_norms: List[Tuple[set, Dict[str, Any]]] = []

    for ev in events:
        norm = re.sub(r"[^a-z0-9\u0600-\u06FF\u0400-\u04FF ]+", " ", ev["title"].lower()).strip()
        words = set(w for w in norm.split() if len(w) > 2)
        duplicate_target = None
        if len(words) >= 4:
            for kw_set, target in seen_norms:
                overlap = len(words & kw_set) / max(1, min(len(words), len(kw_set)))
                if overlap >= 0.68 and abs(ev["timestamp"] - target["timestamp"]) < 21600:
                    duplicate_target = target
                    break
        if duplicate_target:
            duplicate_target["corroborations"] = duplicate_target.get("corroborations", 1) + 1
            if not duplicate_target.get("lat") and ev.get("lat"):
                duplicate_target["lat"] = ev["lat"]
                duplicate_target["lon"] = ev["lon"]
                duplicate_target["locationName"] = ev["locationName"]
                duplicate_target["geoPrecision"] = ev["geoPrecision"]
            if sev_rank.get(ev["severity"], 0) > sev_rank.get(duplicate_target["severity"], 0):
                duplicate_target["severity"] = ev["severity"]
            continue

        ev["corroborations"] = 1
        kept.append(ev)
        if words:
            seen_norms.append((words, ev))
    return kept


def gather_all_feeds(
    watch_query: str = "",
    custom_keywords: Optional[List[str]] = None,
    custom_feed_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    now = time.time()
    clean_watch = re.sub(r"[^\w\s\-,.]", "", (watch_query or "").strip())[:60]
    kw_list = [k.strip() for k in (custom_keywords or []) if k.strip()][:20]
    url_list = [u.strip() for u in (custom_feed_urls or []) if u.strip()][:5]

    cache_key = json.dumps([clean_watch.lower(), kw_list, url_list], sort_keys=True)
    cached = _CACHE.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL_BASE:
        payload = dict(cached[1])
        payload["cacheAgeSec"] = int(now - cached[0])
        return payload

    tasks: List[Tuple[str, Any]] = []
    for name, url, cat in STATIC_RSS_FEEDS:
        tasks.append((name, lambda u=url, n=name, c=cat: _parse_rss_or_atom(_fetch_bytes(u, 10), n, c, kw_list)))

    if clean_watch:
        q_encoded = urllib.parse.quote_plus(
            f'"{clean_watch}" (attack OR airstrike OR missile OR drone OR explosion OR siren OR alert OR shelling OR evacuation) when:1d'
        )
        local_url = f"https://news.google.com/rss/search?q={q_encoded}&hl=en-US&gl=US&ceid=US:en"
        tasks.append((f"Local Watch · {clean_watch}", lambda u=local_url, w=clean_watch: _parse_rss_or_atom(_fetch_bytes(u, 10), f"Google News · {w}", "osint", kw_list)))

    for idx, curl in enumerate(url_list):
        if _is_safe_public_url(curl):
            cname = f"Custom Feed #{idx + 1}"
            tasks.append((cname, lambda u=curl, n=cname: _parse_rss_or_atom(_fetch_bytes(u, 10), n, "custom", kw_list, force_include=True)))

    tasks.append(("GDELT 2.0 Geo", lambda: _fetch_gdelt_live(kw_list)))
    tasks.append(("GDACS Civil", _fetch_gdacs))
    tasks.append(("USGS Seismic", _fetch_usgs))

    all_events: List[Dict[str, Any]] = []
    sources_status: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=10) as pool:
        future_map = {pool.submit(fn): label for label, fn in tasks}
        for fut in as_completed(future_map):
            label = future_map[fut]
            try:
                res = fut.result()
                all_events.extend(res)
                sources_status.append({"name": label, "ok": True, "count": len(res)})
            except Exception as exc:
                sources_status.append({"name": label, "ok": False, "count": 0, "error": str(exc)[:80]})

    deduped = _deduplicate(all_events)
    sources_status.sort(key=lambda s: s["name"])

    result = {
        "events": deduped[:160],
        "sources": sources_status,
        "generatedAt": int(now),
        "cacheAgeSec": 0,
    }
    _CACHE[cache_key] = (now, result)
    return result
