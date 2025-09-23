import requests
from bs4 import BeautifulSoup
from typing import List, Optional
import re
import difflib


class Event:
    def __init__(self, day: str, time: str, name: str, channel: str, sport: str, acestream_link: Optional[str] = None, mapped_channel_name: Optional[str] = None):
        self.day = day
        self.time = time
        self.name = name
        self.channel = channel
        self.sport = sport
        self.acestream_link = acestream_link
        self.mapped_channel_name = mapped_channel_name  # <-- NUEVO


# --- Normalizador de nombres de canales ---
def normalize_channel_name(name: str) -> str:
    name = name.lower()
    name = re.sub(r"\b(1080|720|hd|fhd|uhd|4k|multi.?audio)\b", "", name)
    name = re.sub(r"\(.*?\)", "", name)
    name = re.sub(r"\*|\-|🏁", "", name)
    name = name.replace(" ", "")
    replacements = {
        "m+": "movistar",
        "m.": "movistar",
        "#vamos": "vamos",
        "golplay": "gol",
        "laliga": "laliga",
        "hypermotion": "hypermotion",
        "dazn": "dazn",
        "movistarplus+": "movistarplus",
    }
    for old, new in replacements.items():
        name = name.replace(old, new)
    return name



channel_corrections = {
    "gol play": "gol",
    "laliga tv hypermotion 2": "la liga hypermotion 2",
    "laliga tv hypermotion": "la liga hypermotion",
    "m+ deportes 2": "movistar deportes 2",
    "m+ deportes 3": "movistar deportes 3",
    "m+ laliga tv": "movistar la liga",
    "la 1": "la 1",
}


def find_closest_channel(channel_name: str, channels_names: List[str]) -> Optional[str]:
    if not channels_names:
        return None
    norm_name = normalize_channel_name(channel_name)
    corrected_name = channel_corrections.get(norm_name, norm_name)
    norm_channels = [normalize_channel_name(c) for c in channels_names]
    closest_matches = difflib.get_close_matches(corrected_name, norm_channels, n=1, cutoff=0.4)
    if closest_matches:
        idx = norm_channels.index(closest_matches[0])
        return channels_names[idx]
    return None


def get_tv_programs(url: str = "https://www.marca.com/programacion-tv.html", channel_map: dict = None) -> List[Event]:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        day_sections = soup.find_all("li", class_="content-item")[1:]
        events_data = []
        seen_events = set()

        for day_section in day_sections:
            day_span = day_section.find("span", class_="title-section-widget")
            if not day_span:
                continue
            day = day_span.text.strip()

            events = day_section.find_all("li", class_="dailyevent")
            for event in events:
                time_tag = event.find("strong", class_="dailyhour")
                event_name_tag = event.find("h4", class_="dailyteams")
                channel_tag = event.find("span", class_="dailychannel")
                sport_tag = event.find("span", class_="dailyday")

                time_text = time_tag.text.strip() if time_tag else "N/A"
                event_name = event_name_tag.text.strip() if event_name_tag else "N/A"
                channel = channel_tag.text.strip() if channel_tag else "N/A"
                sport = sport_tag.text.strip() if sport_tag else "N/A"

                event_id = (day, time_text, event_name, channel)
                if event_id not in seen_events:
                    closest_channel = find_closest_channel(channel, channel_map["names"])
                    acestream_link = None
                    mapped_channel_name = None
                    if closest_channel:
                        index = channel_map["names"].index(closest_channel)
                        acestream_link = channel_map["links"][index]
                        mapped_channel_name = channel_map["names"][index]  # <-- NUEVO

                    events_data.append(Event(day, time_text, event_name, channel, sport, acestream_link, mapped_channel_name))
                    seen_events.add(event_id)

        return events_data

    except requests.RequestException as e:
        print(f"Failed to retrieve TV programs from {url}: {e}")
        return []