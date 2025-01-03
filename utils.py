import datetime

def milliseconds_to_human_readable(ms):
    delta = datetime.timedelta(milliseconds=ms)
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    human_readable = []

    if days > 0:
        human_readable.append(f"{days}:")

    if hours > 0:
        human_readable.append(f'{str(hours).zfill(2)}:')
    else:
        human_readable.append('   ')

    if minutes > 0:
        human_readable.append(f'{str(minutes).zfill(2)}:')
    else:
        human_readable.append('00:')
    
    human_readable.append(f'{str(seconds).zfill(2)}')

    return ''.join(human_readable)

