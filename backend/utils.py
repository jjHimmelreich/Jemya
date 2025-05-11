import re
import json

def milliseconds_to_human_readable(ms):
    seconds = (ms / 1000) % 60
    minutes = (ms / (1000 * 60)) % 60
    hours = (ms / (1000 * 60 * 60)) % 24
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

def extract_playlist(text):
    pattern = r"(.*)```json\s*(\[.*?\])\s*```(.*)"
    match = re.search(pattern, text, re.DOTALL)

    if not match:
        return None, text, ""  # No JSON found

    text_before = match.group(1).strip()
    json_str = match.group(2).strip()
    text_after = match.group(3).strip()

    try:
        parsed_json = json.loads(json_str)
    except json.JSONDecodeError:
        return None, text, ""

    return parsed_json, text_before, text_after

def add_prefix_if_missing(prefix, s):
    if not s.startswith(prefix):
        return prefix + s
    return s