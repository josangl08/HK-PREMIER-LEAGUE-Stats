from data.extractors.ics_extractor import ICSExtractor
import re
import logging

logging.basicConfig(level=logging.INFO)
ext = ICSExtractor()
events = ext.fetch()

on_cc_count = 0
fb_count = 0
yt_count = 0

url_pattern = re.compile(r"https?://\S+")

for ev in events:
    desc = ev.get("description") or ""
    if "on.cc" in desc.lower():
        on_cc_count += 1
        print(f"Found on.cc in description: {desc[:100]}...")
    
    urls = url_pattern.findall(desc)
    for url in urls:
        if "facebook.com" in url or "fb.com" in url:
            fb_count += 1
        elif "youtube.com" in url or "youtu.be" in url:
            yt_count += 1

print(f"Total events: {len(events)}")
print(f"Total events with on.cc in description: {on_cc_count}")
print(f"Total FB URLs found: {fb_count}")
print(f"Total YT URLs found: {yt_count}")
