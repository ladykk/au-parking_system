from datetime import datetime, timedelta


def datetime_to_string(input: datetime):
    return input.strftime("%d/%m/%Y %H:%M:%S")

def datetime_to_upload_string(input: datetime):
    return input.strftime("%Y-%m-%dT%H:%M:%S")


def datetime_now():
    current_datetime = datetime.now()
    return current_datetime, datetime_to_string(current_datetime)


def seconds_from_now(timestamp: datetime, seconds: int):
    return timestamp + timedelta(seconds=seconds) < datetime.now()
