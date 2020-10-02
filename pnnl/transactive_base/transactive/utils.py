from dateutil.parser import parse


def calculate_hour_of_year(_dt):
    if isinstance(_dt, str):
        _dt = parse(_dt)
    _now_hour = _dt.replace(minute=0, second=0)
    start_hour = _now_hour.replace(month=1, day=1, hour=0, minute=0, second=0)
    hour_of_year = int((_now_hour - start_hour).total_seconds() / 3600)
    return hour_of_year


def lists_to_dict(lst1, lst2):
    dct = {}
    for item1, item2 in zip(lst1, lst2):
        dct[item1] = item2
    return dct

