#!/usr/bin/env python3
#
# fm-stats
#
# Extract and dump useful stats from funding-manifest.csv file
#

import csv
import datetime
import dateutil.parser
import time
import json
from pprint import pprint
import math
import argparse
import copy
import string

# FLOSS fund is looking to fund entities in the range
# 10k - 100k.
ft = 10000  # 10k USD min

# Currency conversion as of 26 Nov 2024
# This isn't correct either for the past, or for
# the future, but it's a good enough approximation for now
currency_weight = {
    "USD": 84.31,
    "EUR": 88.59,
    "CAD": 59.76,
    "GBP": 105.82,
    "INR": 1,
}


def dtformat(dt):
    return dt.strftime("%a, %-d %b %Y %H:%M:%S %Z")


parser = argparse.ArgumentParser()
parser.add_argument(
    "manifest", metavar="funding-manifest.csv", help="Path to funding-manifest.csv"
)
args = parser.parse_args()

csvfile = open(args.manifest, encoding="utf-8")
reader = csv.reader(csvfile)
nr = 0
disabled = 0
errors = 0
mdesc = []
meets_ft = 0
manifests_zfr = 0  # zero fund requested !
etype_count = {}
etype_meets_ft = {}
erole_count = {}
etype_proj_count = {}
etype_max_fr = {}
lic_map = {}
annual_fin_totals = {}
fh_currencies = {}

ft_keys = ["income", "expenses", "taxes"]
manifest_fin_count = {
    "income": 0,
    "expenses": 0,
    "taxes": 0,
}

# limitation on commercial use isn't "free" ?
# just a flag for examination, not an argument to
# consider/reject the manifest
non_free_licenses = ["CC-BY-NC-SA-3.0"]

# usage count for every tag used in projects
tag_count = {}

for idx, row in enumerate(reader):
    if idx == 0:
        continue
    nr += 1
    rid, url, created_at, updated_at, status, manifest_json = row
    if status != "active":
        disabled += 1
        continue
    try:
        manifest = json.loads(manifest_json)
    except json.decoder.JSONDecodeError as err:
        print(f"At row={rid}, error:{err}")
        errors += 1
        continue

    created_at = dateutil.parser.parse(created_at, fuzzy=True)
    updated_at = dateutil.parser.parse(updated_at, fuzzy=True)

    this_mdesc = {
        "id": rid,
        "url": url,
        "created_at": created_at,
        "updated_at": updated_at,
        "updated_at": updated_at,
        "manifest": manifest,
    }

    nfl = 0
    for prj in manifest["projects"]:
        for tag in prj["tags"]:
            if tag in tag_count:
                tag_count[tag] += 1
            else:
                tag_count[tag] = 1

        for lic in prj["licenses"]:
            # NOTE: potential validation bug
            # one project has a misspelled "sdpx" rather than "spdx"
            if lic.startswith("spdx:") or lic.startswith("sdpx:"):
                lic = lic[5:]
            elif lic.startswith("GNU:"):
                lic = lic[4:]  # I see a GNU:AGPL-3.0
            if lic in lic_map:
                lic_map[lic] += 1
            else:
                lic_map[lic] = 1
            if lic in non_free_licenses:
                nfl += 1
    this_mdesc["nfl"] = nfl
    # print(json.dumps(manifest, indent=2))
    plan_max = {}
    for plans in manifest["funding"]["plans"]:
        freq = plans["frequency"]
        cmult = currency_weight[plans["currency"]] / currency_weight["USD"]
        # Normalize fin totals to USD, as the FLOSS fund gives >= $$$$$ !
        amount = plans["amount"] * cmult
        if freq in plan_max:
            plan_max[freq] = max(plan_max[freq], amount)
        else:
            plan_max[freq] = amount
    max_fr = 0
    if "one-time" in plan_max:
        max_fr = max(plan_max["one-time"], max_fr)
    if "monthly" in plan_max:
        max_fr = max(plan_max["monthly"] * 12, max_fr)
    if "yearly" in plan_max:
        max_fr = max(plan_max["yearly"], max_fr)
    plan_max["max-fr"] = max_fr
    if max_fr >= ft:
        meets_ft += 1
    this_mdesc["funding-plan-max"] = plan_max
    mdesc.append(this_mdesc)

    # Update stats
    etype = manifest["entity"]["type"]
    if etype in etype_count:
        etype_count[etype] += 1
        etype_proj_count[etype] += len(manifest["projects"])
        etype_max_fr[etype] = max(etype_max_fr[etype], max_fr)
    else:
        etype_count[etype] = 1
        etype_proj_count[etype] = len(manifest["projects"])
        etype_max_fr[etype] = max_fr

    if max_fr >= ft:
        if etype in etype_meets_ft:
            etype_meets_ft[etype] += 1
        else:
            etype_meets_ft[etype] = 1

    erole = manifest["entity"]["role"]
    if erole in erole_count:
        erole_count[erole] += 1
    else:
        erole_count[erole] = 1

    fin_totals = {
        "income": 0,
        "expenses": 0,
        "taxes": 0,
    }
    if "history" in manifest["funding"] and manifest["funding"]["history"]:
        for hist in manifest["funding"]["history"]:
            year = hist["year"]
            if year not in annual_fin_totals:
                annual_fin_totals[year] = {
                    "income": 0,
                    "expenses": 0,
                    "taxes": 0,
                }
            # Normalize fin totals to USD, as the FLOSS fund gives >= $$$$$ !
            c_weight = (
                currency_weight[hist["currency"]] / currency_weight["USD"]
            )  # required field
            for key in ft_keys:
                if key in hist:
                    value = hist[key] * c_weight
                    annual_fin_totals[year][key] += value
                    fin_totals[key] += value
            fh_currencies[hist["currency"]] = 1
        for key in ft_keys:
            if fin_totals[key] > 0:
                manifest_fin_count[key] += 1
            fin_totals[key] = math.floor(fin_totals[key])
    this_mdesc["fin_totals"] = fin_totals

    if max_fr == 0:
        manifests_zfr += 1

fin_totals = {
    "income": 0,
    "expenses": 0,
    "taxes": 0,
}

for year in annual_fin_totals:
    for key in ft_keys:
        value = math.floor(annual_fin_totals[year][key])
        annual_fin_totals[year][key] = value
        fin_totals[key] += value

mdesc.sort(key=lambda x: x["funding-plan-max"]["max-fr"], reverse=True)
print(f"Total manifests = {nr} Disabled = {disabled} Errors = {errors}")
print(f"Manifests above funding threshold = {meets_ft}")
print(f"Manifests requesting NO SPECIFIC (0) funding = {manifests_zfr}")
print("Cumulative financials for all years reported in manifests:")
pprint(fin_totals)
print("Entity Role:")
print(erole_count)
print("Entity Type:")
print(etype_count)
print("Projects per Entity Type:")
print(etype_proj_count)
print("Requested Max funding per Entity Type:")
print(etype_max_fr)
print("Above threshold manifests per Entity Type:")
print(etype_meets_ft)
print("Licenses:")
pprint(lic_map)
print("Annual Financial Totals:")
pprint(annual_fin_totals)
print("Finances Reported by entities:")
pprint(manifest_fin_count)
print("Currencies:", list(fh_currencies.keys()))
print()
print(f"-- Manifests above funding threshold {ft//1000}k USD --")
print()
for idx, minfo in enumerate(mdesc):
    if idx == meets_ft:
        print()
        print(f"-- Manifests below funding threshold {ft//1000}k USD --")
        print()
    created_at = minfo["created_at"]
    updated_at = minfo["updated_at"]
    mf = minfo["funding-plan-max"]["max-fr"]
    manifest = minfo["manifest"]
    print(idx + 1, minfo["url"], f"(Project ID: {minfo['id']})")
    print("  Non-free licences: ", minfo["nfl"])
    print("  Entity Type : ", manifest["entity"]["type"])
    print("  Max funding requested : ", mf)
    print("  Financial totals: ", minfo["fin_totals"])
    print("  Created:", dtformat(created_at))
    if created_at != updated_at:
        diff = updated_at - created_at
        print("  Updated:", dtformat(updated_at), f"({diff})")

# Compute, for every day
# - incoming manifests
# - entity type of incoming manifests
# - additional projects
# - cumulative funding stats

# Compute, for every day since the launch of the FLOSS fund,
#
# Additional
#   manifests, projects
#   entity types (org/individual/group)
#   manifests above funding threshold
#
# FIXME Right now, we do not consider scenarios where a manifest went
# through a change in financial requirements. Not many days have
# passed since launch, so this is a reasonable assumption to make.
# Over a long term, changes to manifest would need to be tracked.
mdesc.sort(key=lambda x: x["created_at"])

# FLOSS fund was launched on 15th October 2024, nominally
# 10 AM IST => UTC + 5:30.
launch_dt = datetime.datetime(2024, 10, 15, 15, 30, tzinfo=datetime.UTC)
day_since_launch = 0


# d_ => daily
# c_ => cumulative
def reset_counters():
    d_manifests = 0
    d_projects = 0
    d_etype = {"organisation": 0, "individual": 0, "group": 0}
    d_manifests_above_ft = 0
    d_fin_totals = {
        "income": 0,
        "expenses": 0,
        "taxes": 0,
    }
    d_mfr_total = 0
    return (
        d_manifests,
        d_projects,
        d_etype,
        d_fin_totals,
        d_manifests_above_ft,
        d_mfr_total,
    )


c_manifests, c_projects, c_etype, c_fin_totals, c_manifests_above_ft, c_mfr_total = (
    reset_counters()
)
d_manifests, d_projects, d_etype, d_fin_totals, d_manifests_above_ft, d_mfr_total = (
    reset_counters()
)

# We'll save a timeseries for plotting
timeseries = {
    "t": [],  # day since launch
    "d_manifests": [],
    "d_projects": [],
    "d_mfr_total": [],
    "d_etype": [],
    "d_manifests_above_ft": [],
    "d_fin_totals": [],
    "c_manifests": [],
    "c_projects": [],
    "c_mfr_total": [],
    "c_etype": [],
    "c_manifests_above_ft": [],
    "c_fin_totals": [],
}

for idx, minfo in enumerate(mdesc):
    tdiff = minfo["created_at"] - launch_dt
    if (tdiff.days > day_since_launch) or (idx == len(mdesc) - 1):
        c_manifests += d_manifests
        c_projects += d_projects
        c_mfr_total += d_mfr_total
        c_mfr_total = math.floor(c_mfr_total)
        d_mfr_total = math.floor(d_mfr_total)
        for key in d_etype:
            c_etype[key] += d_etype[key]
        c_manifests_above_ft += d_manifests_above_ft
        # save in time series
        timeseries["t"].append(day_since_launch)
        timeseries["d_manifests"].append(copy.copy(d_manifests))
        timeseries["d_projects"].append(copy.copy(d_projects))
        timeseries["d_mfr_total"].append(copy.copy(d_mfr_total))
        timeseries["d_etype"].append(copy.copy(d_etype))
        timeseries["d_manifests_above_ft"].append(d_manifests_above_ft)
        timeseries["d_fin_totals"].append(d_fin_totals)
        timeseries["c_manifests"].append(copy.copy(c_manifests))
        timeseries["c_projects"].append(copy.copy(c_projects))
        timeseries["c_mfr_total"].append(copy.copy(c_mfr_total))
        timeseries["c_etype"].append(copy.copy(c_etype))
        timeseries["c_manifests_above_ft"].append(c_manifests_above_ft)
        timeseries["c_fin_totals"].append(c_fin_totals)
        # dump cumulative stats
        print(f"Day {day_since_launch}:")
        print("  New manifests:", d_manifests)
        print("  New projects:", d_projects)
        print("  New entity types:", d_etype)
        print("  Manifests > funding threshold:", d_manifests_above_ft)
        print("  Funding requested :", d_mfr_total)
        print("  Additional financials:", d_fin_totals)
        print("  Cumulative:")
        print("    Manifests:", c_manifests)
        print("    Projects:", c_projects)
        print("    Entity types:", c_etype)
        print("    Manifests > funding threshold:", c_manifests_above_ft)
        print("    Funding requested :", c_mfr_total)
        print("    Financials:", c_fin_totals)
        (
            d_manifests,
            d_projects,
            d_etype,
            d_fin_totals,
            d_manifests_above_ft,
            d_mfr_total,
        ) = reset_counters()
        day_since_launch = tdiff.days
    manifest = minfo["manifest"]
    d_manifests += 1
    d_projects += len(manifest["projects"])
    me_type = manifest["entity"]["type"]
    d_etype[me_type] += 1
    if minfo["funding-plan-max"]["max-fr"] >= ft:
        d_manifests_above_ft += 1
    d_mfr_total += minfo["funding-plan-max"]["max-fr"]
    for key in d_fin_totals:
        d_fin_totals[key] += minfo["fin_totals"][key]
        c_fin_totals[key] += minfo["fin_totals"][key]

# fill holes in the timeseries. Not on every day may new manifests be submitted.
# On a day where d_ values don't change, they must be set to 0
ts2 = copy.deepcopy(timeseries)
for idx, (start, end) in enumerate(zip(timeseries["t"][:-1], timeseries["t"][1:])):
    if end > start + 1:
        # we have no action for one or more days
        # print(start, end)
        for di in range(end - start - 1):
            this_idx = start + di + 1
            ts2["t"].insert(this_idx, this_idx)
            for key in [
                "manifests",
                "projects",
                "mfr_total",
                "etype",
                "manifests_above_ft",
                "fin_totals",
            ]:
                key_name = f"c_{key}"
                ts2[key_name].insert(this_idx, timeseries[key_name][idx])
            (
                d_manifests,
                d_projects,
                d_etype,
                d_fin_totals,
                d_manifests_above_ft,
                d_mfr_total,
            ) = reset_counters()
            ts2["d_manifests"].insert(this_idx, d_manifests)
            ts2["d_projects"].insert(this_idx, d_projects)
            ts2["d_etype"].insert(this_idx, d_etype)
            ts2["d_fin_totals"].insert(this_idx, d_fin_totals)
            ts2["d_manifests_above_ft"].insert(this_idx, d_manifests_above_ft)
            ts2["d_mfr_total"].insert(this_idx, d_mfr_total)

# Done expanding, so rename
timeseries = ts2
del ts2
# pprint(timeseries)

# Show info for tags.
# project-tags.txt is a copy of https://floss.fund/static/project-tags.txt
known_tags = [x.strip() for x in open("project-tags.txt", "r").readlines()]
used_tags = list(tag_count.keys())
unused_tags = []
for tag in known_tags:
    if tag not in used_tags:
        unused_tags.append(tag)
tc_list = list(zip(tag_count.keys(), tag_count.values()))
tc_list.sort(key=lambda x: x[1], reverse=True)
print("Used tags, and their frequencies are:")
pprint(tc_list)
print("These tags (suggested by floss.fund) are NOT used by any project:")
pprint(unused_tags)
