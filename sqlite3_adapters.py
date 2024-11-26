import datetime
import sqlite3

# sqlite does not have native datatypes for date/time, etc
# back/forth conversions are required. This does it.

#
# Directly adapted from
# https://docs.python.org/3/library/sqlite3.html#sqlite3-adapter-converter-recipes
#


def adapt_date_iso(val):
    """Adapt datetime.date to ISO 8601 date."""
    return val.isoformat()


def adapt_datetime_iso(val):
    """Adapt datetime.datetime to timezone-naive ISO 8601 date."""
    return val.isoformat()


def adapt_datetime_epoch(val):
    """Adapt datetime.datetime to Unix timestamp."""
    return int(val.timestamp())


def convert_date(val):
    """Convert ISO 8601 date to datetime.date object."""
    return datetime.date.fromisoformat(val.decode())


def convert_datetime(val):
    """Convert ISO 8601 datetime to datetime.datetime object."""
    return datetime.datetime.fromisoformat(val.decode())


def convert_timestamp(val):
    """Convert Unix epoch timestamp to datetime.datetime object."""
    return datetime.datetime.fromtimestamp(int(val))


def register_datetime():
    """Register to/fro conversions"""
    # sqlite3.register_adapter(datetime.date, adapt_date_iso)
    sqlite3.register_adapter(datetime.datetime, adapt_datetime_iso)
    # sqlite3.register_adapter(datetime.datetime, adapt_datetime_epoch)

    # sqlite3.register_converter("date", convert_date)
    sqlite3.register_converter("datetime", convert_datetime)
    # sqlite3.register_converter("timestamp", convert_timestamp)
