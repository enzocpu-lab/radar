import math
import re
from typing import Optional, Dict, Any, List, Tuple

# (name, lat, lon, kind, country, aliases)
# kind: 'city', 'region', 'waterway', 'country'
PLACES: List[Tuple[str, float, float, str, str, Tuple[str, ...]]] = [
    # Strategic landmarks & waterways
    ("Crimean Bridge / Kerch Strait", 45.3020, 36.5120, "region", "Crimea", ("crimean bridge", "crimea bridge", "kerch bridge", "kerch strait", "kerch")),
    ("Strait of Hormuz", 26.5667, 56.2500, "waterway", "Persian Gulf", ("strait of hormuz", "hormuz")),
    ("Bab el-Mandeb", 12.6000, 43.3500, "waterway", "Red Sea", ("bab el-mandeb", "bab al-mandab")),
    ("Red Sea", 20.2000, 38.5000, "waterway", "Red Sea", ("red sea",)),
    ("Persian Gulf", 26.8000, 51.5000, "waterway", "Persian Gulf", ("persian gulf", "arabian gulf")),
    ("Gulf of Oman", 24.7000, 58.3000, "waterway", "Gulf of Oman", ("gulf of oman",)),
    ("Gulf of Aden", 12.5000, 47.0000, "waterway", "Gulf of Aden", ("gulf of aden",)),
    ("Black Sea", 43.4000, 34.3000, "waterway", "Black Sea", ("black sea",)),
    ("Sea of Azov", 46.0000, 36.5000, "waterway", "Sea of Azov", ("sea of azov", "azov sea")),
    ("Taiwan Strait", 24.5000, 119.8000, "waterway", "Taiwan Strait", ("taiwan strait",)),
    ("South China Sea", 13.0000, 114.0000, "waterway", "South China Sea", ("south china sea",)),
    ("Golan Heights", 33.0000, 35.7500, "region", "Golan Heights", ("golan heights", "golan")),
    ("South Lebanon", 33.2500, 35.4000, "region", "Lebanon", ("southern lebanon", "south lebanon")),
    ("West Bank", 31.9466, 35.3027, "region", "West Bank", ("west bank",)),
    ("Gaza Strip", 31.4200, 34.3800, "region", "Gaza", ("gaza strip", "gaza")),
    ("Donbas", 48.1000, 37.8000, "region", "Ukraine", ("donbas", "donbass")),
    ("Crimea", 44.9521, 34.1024, "region", "Crimea", ("crimea", "crimean")),

    # Iran
    ("Tehran", 35.6892, 51.3890, "city", "Iran", ("tehran",)),
    ("Isfahan", 32.6546, 51.6680, "city", "Iran", ("isfahan", "esfahan")),
    ("Shiraz", 29.5918, 52.5837, "city", "Iran", ("shiraz",)),
    ("Tabriz", 38.0962, 46.2738, "city", "Iran", ("tabriz",)),
    ("Mashhad", 36.2605, 59.6168, "city", "Iran", ("mashhad",)),
    ("Ahvaz", 31.3183, 48.6706, "city", "Iran", ("ahvaz", "ahwaz")),
    ("Kermanshah", 34.3142, 47.0650, "city", "Iran", ("kermanshah",)),
    ("Bushehr", 28.9234, 50.8203, "city", "Iran", ("bushehr",)),
    ("Bandar Abbas", 27.1832, 56.2666, "city", "Iran", ("bandar abbas",)),
    ("Chabahar", 25.2919, 60.6430, "city", "Iran", ("chabahar",)),
    ("Natanz", 33.5112, 51.9182, "city", "Iran", ("natanz",)),
    ("Fordow", 34.8840, 50.9960, "city", "Iran", ("fordow", "fordo")),
    ("Qom", 34.6416, 50.8746, "city", "Iran", ("qom",)),
    ("Karaj", 35.8400, 50.9391, "city", "Iran", ("karaj",)),
    ("Kerman", 30.2839, 57.0834, "city", "Iran", ("kerman",)),
    ("Zahedan", 29.4963, 60.8629, "city", "Iran", ("zahedan",)),
    ("Urmia", 37.5527, 45.0761, "city", "Iran", ("urmia", "orumiyeh")),

    # Persian Gulf / Arabian Peninsula
    ("Manama", 26.2285, 50.5860, "city", "Bahrain", ("manama",)),
    ("Doha", 25.2854, 51.5310, "city", "Qatar", ("doha", "al udeid")),
    ("Abu Dhabi", 24.4539, 54.3773, "city", "UAE", ("abu dhabi",)),
    ("Dubai", 25.2048, 55.2708, "city", "UAE", ("dubai",)),
    ("Muscat", 23.5880, 58.3829, "city", "Oman", ("muscat",)),
    ("Kuwait City", 29.3759, 47.9774, "city", "Kuwait", ("kuwait city",)),
    ("Riyadh", 24.7136, 46.6753, "city", "Saudi Arabia", ("riyadh",)),
    ("Jeddah", 21.4858, 39.1925, "city", "Saudi Arabia", ("jeddah",)),
    ("Dhahran", 26.2361, 50.0393, "city", "Saudi Arabia", ("dhahran", "dammam")),
    ("Sanaa", 15.3694, 44.1910, "city", "Yemen", ("sanaa", "sana'a")),
    ("Hodeidah", 14.7979, 42.9545, "city", "Yemen", ("hodeidah", "hudaydah")),
    ("Aden", 12.7855, 45.0187, "city", "Yemen", ("aden",)),

    # Levant & Iraq
    ("Baghdad", 33.3152, 44.3661, "city", "Iraq", ("baghdad",)),
    ("Erbil", 36.1911, 44.0092, "city", "Iraq", ("erbil", "irbil")),
    ("Basra", 30.5085, 47.7804, "city", "Iraq", ("basra",)),
    ("Mosul", 36.3350, 43.1189, "city", "Iraq", ("mosul",)),
    ("Kirkuk", 35.4681, 44.3922, "city", "Iraq", ("kirkuk",)),
    ("Damascus", 33.5138, 36.2765, "city", "Syria", ("damascus",)),
    ("Aleppo", 36.2021, 37.1343, "city", "Syria", ("aleppo",)),
    ("Homs", 34.7324, 36.7137, "city", "Syria", ("homs",)),
    ("Latakia", 35.5317, 35.7901, "city", "Syria", ("latakia",)),
    ("Deir ez-Zor", 35.3359, 40.1408, "city", "Syria", ("deir ez-zor", "deir ezzor")),
    ("Beirut", 33.8938, 35.5018, "city", "Lebanon", ("beirut",)),
    ("Tyre", 33.2705, 35.2038, "city", "Lebanon", ("tyre",)),
    ("Baalbek", 34.0047, 36.2110, "city", "Lebanon", ("baalbek",)),
    ("Sidon", 33.5614, 35.3714, "city", "Lebanon", ("sidon",)),
    ("Nabatieh", 33.3779, 35.4839, "city", "Lebanon", ("nabatieh",)),
    ("Tel Aviv", 32.0853, 34.7818, "city", "Israel", ("tel aviv", "tel-aviv")),
    ("Jerusalem", 31.7683, 35.2137, "city", "Israel", ("jerusalem",)),
    ("Haifa", 32.7940, 34.9896, "city", "Israel", ("haifa",)),
    ("Beersheba", 31.2518, 34.7913, "city", "Israel", ("beersheba", "beer sheva")),
    ("Ashkelon", 31.6688, 34.5743, "city", "Israel", ("ashkelon",)),
    ("Eilat", 29.5577, 34.9519, "city", "Israel", ("eilat",)),
    ("Gaza City", 31.5017, 34.4668, "city", "Gaza", ("gaza city",)),
    ("Rafah", 31.2969, 34.2455, "city", "Gaza", ("rafah",)),
    ("Khan Younis", 31.3462, 34.3063, "city", "Gaza", ("khan younis", "khan yunis")),
    ("Ramallah", 31.9038, 35.2034, "city", "West Bank", ("ramallah",)),
    ("Jenin", 32.4573, 35.2999, "city", "West Bank", ("jenin",)),
    ("Nablus", 32.2211, 35.2544, "city", "West Bank", ("nablus",)),
    ("Amman", 31.9454, 35.9284, "city", "Jordan", ("amman",)),
    ("Cairo", 30.0444, 31.2357, "city", "Egypt", ("cairo",)),
    ("Alexandria", 31.2001, 29.9187, "city", "Egypt", ("alexandria",)),
    ("Suez", 29.9668, 32.5498, "city", "Egypt", ("suez", "suez canal")),

    # Eastern Europe / Russia / Caucasus / Turkey
    ("Kyiv", 50.4501, 30.5234, "city", "Ukraine", ("kyiv", "kiev")),
    ("Kharkiv", 49.9935, 36.2304, "city", "Ukraine", ("kharkiv", "kharkov")),
    ("Odesa", 46.4825, 30.7233, "city", "Ukraine", ("odesa", "odessa")),
    ("Dnipro", 48.4647, 35.0462, "city", "Ukraine", ("dnipro", "dnipropetrovsk")),
    ("Lviv", 49.8397, 24.0297, "city", "Ukraine", ("lviv",)),
    ("Zaporizhzhia", 47.8388, 35.1396, "city", "Ukraine", ("zaporizhzhia", "zaporizhia")),
    ("Mykolaiv", 46.9750, 31.9946, "city", "Ukraine", ("mykolaiv", "nikolaev")),
    ("Sumy", 50.9077, 34.7981, "city", "Ukraine", ("sumy",)),
    ("Poltava", 49.5883, 34.5514, "city", "Ukraine", ("poltava",)),
    ("Donetsk", 48.0159, 37.8029, "city", "Ukraine", ("donetsk",)),
    ("Luhansk", 48.5740, 39.3078, "city", "Ukraine", ("luhansk",)),
    ("Kherson", 46.6354, 32.6169, "city", "Ukraine", ("kherson",)),
    ("Sevastopol", 44.6167, 33.5254, "city", "Crimea", ("sevastopol",)),
    ("Simferopol", 44.9521, 34.1024, "city", "Crimea", ("simferopol",)),
    ("Moscow", 55.7558, 37.6173, "city", "Russia", ("moscow", "kremlin")),
    ("Saint Petersburg", 59.9343, 30.3351, "city", "Russia", ("saint petersburg", "st petersburg", "st. petersburg")),
    ("Belgorod", 50.5997, 36.5983, "city", "Russia", ("belgorod",)),
    ("Kursk", 51.7373, 36.1874, "city", "Russia", ("kursk",)),
    ("Rostov-on-Don", 47.2357, 39.7015, "city", "Russia", ("rostov-on-don", "rostov")),
    ("Voronezh", 51.6755, 39.2089, "city", "Russia", ("voronezh",)),
    ("Sochi", 43.6028, 39.7342, "city", "Russia", ("sochi",)),
    ("Sofia", 42.6977, 23.3219, "city", "Bulgaria", ("sofia",)),
    ("Varna", 43.2141, 27.9147, "city", "Bulgaria", ("varna",)),
    ("Ankara", 39.9334, 32.8597, "city", "Turkey", ("ankara",)),
    ("Istanbul", 41.0082, 28.9784, "city", "Turkey", ("istanbul",)),
    ("Baku", 40.4093, 49.8671, "city", "Azerbaijan", ("baku",)),
    ("Yerevan", 40.1792, 44.4991, "city", "Armenia", ("yerevan",)),
    ("Tbilisi", 41.7151, 44.8271, "city", "Georgia", ("tbilisi",)),

    # Africa & Asia & Europe & Americas
    ("Port Sudan", 19.6158, 37.2164, "city", "Sudan", ("port sudan",)),
    ("Khartoum", 15.5007, 32.5599, "city", "Sudan", ("khartoum",)),
    ("El Fasher", 13.6279, 25.3494, "city", "Sudan", ("el fasher", "el-fasher", "darfur")),
    ("Mogadishu", 2.0469, 45.3182, "city", "Somalia", ("mogadishu",)),
    ("Tripoli", 32.8872, 13.1913, "city", "Libya", ("tripoli",)),
    ("Addis Ababa", 9.0320, 38.7469, "city", "Ethiopia", ("addis ababa",)),
    ("Kabul", 34.5553, 69.2075, "city", "Afghanistan", ("kabul",)),
    ("Islamabad", 33.6844, 73.0479, "city", "Pakistan", ("islamabad",)),
    ("Karachi", 24.8607, 67.0011, "city", "Pakistan", ("karachi",)),
    ("Lahore", 31.5204, 74.3587, "city", "Pakistan", ("lahore",)),
    ("New Delhi", 28.6139, 77.2090, "city", "India", ("new delhi", "delhi")),
    ("Mumbai", 19.0760, 72.8777, "city", "India", ("mumbai",)),
    ("Taipei", 25.0330, 121.5654, "city", "Taiwan", ("taipei",)),
    ("Seoul", 37.5665, 126.9780, "city", "South Korea", ("seoul",)),
    ("Pyongyang", 39.0392, 125.7625, "city", "North Korea", ("pyongyang",)),
    ("Tokyo", 35.6762, 139.6503, "city", "Japan", ("tokyo",)),
    ("Beijing", 39.9042, 116.4074, "city", "China", ("beijing",)),
    ("London", 51.5072, -0.1276, "city", "United Kingdom", ("london",)),
    ("Paris", 48.8566, 2.3522, "city", "France", ("paris",)),
    ("Berlin", 52.5200, 13.4050, "city", "Germany", ("berlin",)),
    ("Falkenstein", 50.4770, 12.3710, "city", "Germany", ("falkenstein",)),
    ("Warsaw", 52.2297, 21.0122, "city", "Poland", ("warsaw",)),
    ("Bucharest", 44.4268, 26.1025, "city", "Romania", ("bucharest",)),
    ("Athens", 37.9838, 23.7275, "city", "Greece", ("athens",)),
    ("Nicosia", 35.1856, 33.3823, "city", "Cyprus", ("nicosia",)),
    ("Washington", 38.9072, -77.0369, "city", "United States", ("washington", "pentagon")),
    ("New York", 40.7128, -74.0060, "city", "United States", ("new york",)),

    # Countries (matched after specific cities/regions)
    ("Iran", 32.4279, 53.6880, "country", "Iran", ("iran", "iranian", "iranians")),
    ("Israel", 31.0461, 34.8516, "country", "Israel", ("israel", "israeli", "israelis")),
    ("Lebanon", 33.8547, 35.8623, "country", "Lebanon", ("lebanon", "lebanese", "hezbollah")),
    ("Syria", 34.8021, 38.9968, "country", "Syria", ("syria", "syrian", "syrians")),
    ("Iraq", 33.2232, 43.6793, "country", "Iraq", ("iraq", "iraqi", "iraqis")),
    ("Yemen", 15.5527, 48.5164, "country", "Yemen", ("yemen", "yemeni", "yemenis", "houthi", "houthis")),
    ("Bahrain", 26.0667, 50.5577, "country", "Bahrain", ("bahrain", "bahraini", "bahrainis")),
    ("Saudi Arabia", 23.8859, 45.0792, "country", "Saudi Arabia", ("saudi arabia", "saudi", "saudis")),
    ("Qatar", 25.3548, 51.1839, "country", "Qatar", ("qatar", "qatari")),
    ("United Arab Emirates", 23.4241, 53.8478, "country", "UAE", ("united arab emirates", "uae", "emirates")),
    ("Kuwait", 29.3117, 47.4818, "country", "Kuwait", ("kuwait", "kuwaiti")),
    ("Oman", 21.4735, 55.9754, "country", "Oman", ("oman", "omani")),
    ("Jordan", 30.5852, 36.2384, "country", "Jordan", ("jordan", "jordanian")),
    ("Egypt", 26.8206, 30.8025, "country", "Egypt", ("egypt", "egyptian")),
    ("Ukraine", 48.3794, 31.1656, "country", "Ukraine", ("ukraine", "ukrainian", "ukrainians")),
    ("Russia", 55.7558, 37.6173, "country", "Russia", ("russia", "russian", "russians")),
    ("Belarus", 53.7098, 27.9534, "country", "Belarus", ("belarus", "belarusian")),
    ("Poland", 51.9194, 19.1451, "country", "Poland", ("poland", "polish")),
    ("Bulgaria", 42.7339, 25.4858, "country", "Bulgaria", ("bulgaria", "bulgarian")),
    ("Romania", 45.9432, 24.9668, "country", "Romania", ("romania", "romanian")),
    ("Estonia", 58.5953, 25.0136, "country", "Estonia", ("estonia", "estonian")),
    ("Latvia", 56.8796, 24.6032, "country", "Latvia", ("latvia", "latvian")),
    ("Lithuania", 55.1694, 23.8813, "country", "Lithuania", ("lithuania", "lithuanian")),
    ("Finland", 61.9241, 25.7482, "country", "Finland", ("finland", "finnish")),
    ("Norway", 60.4720, 8.4689, "country", "Norway", ("norway", "norwegian")),
    ("Sweden", 60.1282, 18.6435, "country", "Sweden", ("sweden", "swedish")),
    ("Cyprus", 35.1264, 33.4299, "country", "Cyprus", ("cyprus", "cypriot")),
    ("Greece", 39.0742, 21.8243, "country", "Greece", ("greece", "greek")),
    ("Turkey", 38.9637, 35.2433, "country", "Turkey", ("turkey", "turkiye", "türkiye", "turkish")),
    ("Azerbaijan", 40.1431, 47.5769, "country", "Azerbaijan", ("azerbaijan", "azerbaijani")),
    ("Armenia", 40.0691, 45.0382, "country", "Armenia", ("armenia", "armenian")),
    ("Georgia", 42.3154, 43.3569, "country", "Georgia", ("georgia",)),
    ("Sudan", 12.8628, 30.2176, "country", "Sudan", ("sudan", "sudanese")),
    ("Ethiopia", 9.1450, 40.4897, "country", "Ethiopia", ("ethiopia", "ethiopian")),
    ("Somalia", 5.1521, 46.1996, "country", "Somalia", ("somalia", "somali")),
    ("Libya", 26.3351, 17.2283, "country", "Libya", ("libya", "libyan")),
    ("Myanmar", 21.9162, 95.9560, "country", "Myanmar", ("myanmar", "burma")),
    ("Afghanistan", 33.9391, 67.7100, "country", "Afghanistan", ("afghanistan", "afghan")),
    ("Pakistan", 30.3753, 69.3451, "country", "Pakistan", ("pakistan", "pakistani")),
    ("India", 20.5937, 78.9629, "country", "India", ("india", "indian")),
    ("Taiwan", 23.6978, 120.9605, "country", "Taiwan", ("taiwan", "taiwanese")),
    ("South Korea", 35.9078, 127.7669, "country", "South Korea", ("south korea",)),
    ("North Korea", 40.3399, 127.5101, "country", "North Korea", ("north korea",)),
    ("China", 35.8617, 104.1954, "country", "China", ("china", "chinese")),
    ("Germany", 51.1657, 10.4515, "country", "Germany", ("germany", "german")),
    ("United Kingdom", 55.3781, -3.4360, "country", "United Kingdom", ("united kingdom", "britain", "british")),
    ("France", 46.2276, 2.2137, "country", "France", ("france", "french")),
    ("United States", 39.8283, -98.5795, "country", "United States", ("united states",)),
]

# Precompile regex patterns ordered so cities/regions come BEFORE countries, and longer aliases first.
_KIND_PRIORITY = {"city": 0, "region": 1, "waterway": 2, "country": 3}
_MATCH_ENTRIES: List[Tuple[re.Pattern, str, float, float, str, str]] = []

for _name, _lat, _lon, _kind, _country, _aliases in sorted(
    PLACES,
    key=lambda p: (_KIND_PRIORITY.get(p[3], 9), -max(len(a) for a in p[5]))
):
    for _alias in sorted(_aliases, key=len, reverse=True):
        pat = re.compile(r"(?<!\w)" + re.escape(_alias) + r"(?!\w)", re.IGNORECASE)
        _MATCH_ENTRIES.append((pat, _name, _lat, _lon, _kind, _country))

_PREPOSITION_TARGET_RE = re.compile(
    r"\b(?:in|at|on|near|off|over|towards|against|targets?|hits?|strikes?|attacks?)\s+(?:the\s+)?([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})"
)


def _match_first(text: str) -> Optional[Dict[str, Any]]:
    for pat, name, lat, lon, kind, country in _MATCH_ENTRIES:
        if pat.search(text):
            return {
                "locationName": name if kind == "country" else f"{name}, {country}" if country not in name else name,
                "lat": lat,
                "lon": lon,
                "geoPrecision": kind,
                "country": country,
            }
    return None


def geolocate_text(text: str) -> Optional[Dict[str, Any]]:
    """Return best geolocated match, preferring explicit target prepositions ('in Crimea', 'off Bulgaria', 'on Bahrain')."""
    if not text:
        return None
    for m in _PREPOSITION_TARGET_RE.finditer(text):
        phrase = m.group(1)
        hit = _match_first(phrase)
        if hit:
            return hit
    return _match_first(text)


def search_gazetteer(query: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Search built-in places by substring match."""
    q = (query or "").strip().lower()
    if not q:
        return []
    results = []
    seen = set()
    for name, lat, lon, kind, country, aliases in PLACES:
        hay = " ".join([name.lower(), country.lower(), *aliases])
        if q in hay:
            key = (name, country)
            if key in seen:
                continue
            seen.add(key)
            score = 0
            if name.lower().startswith(q) or any(a.startswith(q) for a in aliases):
                score += 10
            if kind == "city":
                score += 3
            results.append({
                "name": name if kind == "country" or country in name else f"{name}, {country}",
                "lat": lat,
                "lon": lon,
                "kind": kind,
                "country": country,
                "_score": score,
            })
    results.sort(key=lambda r: (-r["_score"], r["name"]))
    for r in results:
        r.pop("_score", None)
    return results[:limit]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1 - a)))


def initial_bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
