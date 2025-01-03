import datetime

def milliseconds_to_human_readable(ms):
    seconds = (ms / 1000) % 60
    minutes = (ms / (1000 * 60)) % 60
    hours = (ms / (1000 * 60 * 60)) % 24
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

