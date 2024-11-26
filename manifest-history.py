#!/usr/bin/env python3

import requests
import email.utils
import datetime
from pprint import pprint
import sqlite3
import sqlite3_adapters
import argparse
import sys

# This program assumes the sqlite3 db follows this schema:
# sqlite> .schema mdb_history
# CREATE TABLE mdb_history(fetched_at DATETIME, url TEXT, last_modified DATETIME, data BLOB);


def dtformat(dt):
    return dt.strftime("%a, %-d %b %Y %H:%M:%S %Z")


def update_hist(url, conn):
    result = requests.get(url, stream=True)
    # HTTP dates are in "GMT". We report in UTC, which is same...
    mod_ts = email.utils.parsedate_to_datetime(result.headers["last-modified"])
    print(f"Funding manifest db was last updated at {dtformat(mod_ts)}")
    cursor = conn.cursor()
    qr = cursor.execute("SELECT * from mdb_history where last_modified = ?", (mod_ts,))
    fetchedData = qr.fetchone()
    if not fetchedData:
        print(f"Inserting manifest db for {mod_ts}")
        now = datetime.datetime.now(datetime.UTC)
        res = cursor.execute(
            "INSERT INTO mdb_history VALUES(?, ?, ?, ?)",
            (now, url, mod_ts, result.content),
        )
        conn.commit()
    else:
        print(f"... it is already available in history")
    cursor.close()


def show_latest(conn, save_to):
    cursor = conn.cursor()
    qr = cursor.execute(
        "SELECT last_modified, url, fetched_at, data FROM mdb_history ORDER BY last_modified ASC"
    )
    fetchedData = qr.fetchone()
    if not fetchedData:
        print("No records are available")
    else:
        print(f"Last recorded manifest db was fetched at {dtformat(fetchedData[2])},")
        print(f"from {fetchedData[1]},")
        print(f"which was last modified at {dtformat(fetchedData[0])}")
        if save_to:
            print(f"Saving {fetchedData[1]} to {save_to}...")
            with open(save_to, "wb") as fp:
                fp.write(fetchedData[3])
    cursor.close()


parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument("--update", action="store_true", help="Update from dir.floss.fund")
group.add_argument(
    "--show-latest",
    action="store_true",
    help="Show latest record stored in manifest history",
)
parser.add_argument(
    "--save-to",
    metavar="FILENAME",
    help="Save data to this file, use with --show-latest",
)
args = parser.parse_args()

if args.save_to and not args.show_latest:
    print("ERROR: --save-to may only be used with --show-latest")
    sys.exit(1)
sqlite3_adapters.register_datetime()
# funding-manifests-evolution is a separate git repository
conn = sqlite3.connect(
    "funding-manifests-evolution/dir.floss.fund.db",
    detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
)

if args.update:
    url = "https://dir.floss.fund/funding-manifests.tar.gz"
    update_hist(url, conn)
elif args.show_latest:
    show_latest(conn, args.save_to)

conn.close()
