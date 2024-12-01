#!/usr/bin/env python3
#
# fm-stats
#
# Extract and dump useful stats from funding-manifest.csv file
#
#
# To use this:
#
# 1. Get manifest database from dir.floss.net
#    (https://dir.floss.fund/funding-manifests.tar.gz)
#    or using these steps:
#    a. clone https://github.com/shreekumar3d/funding-manifests-evolution
#    b. ./manifest-history.py --show-latest --save-to funding-manifest.tar.gz
#
# 2. Extract it to some directory, e.g. "data"
# 3. Run this tool : ./fm-stats.py data/funding-manifests.csv
#
# To generate plots and charts, checkout args using --help or below.
# Note that there is an element of randomness in the word clouds.
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
import wordcloud
from PIL import Image
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import statistics

# FLOSS fund is looking to fund entities in the range
# 10k - 100k.
ft = 10 * 1000  # 10k USD min
fmax = 100 * 1000

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
parser.add_argument(
    "--funding-pie", action="store_true", help="Show funding split as a pie-chart"
)
parser.add_argument("--word-cloud", action="store_true", help="Generate word clouds")
parser.add_argument(
    "--funding-trend", action="store_true", help="Plot funding trend (line+bar)"
)
parser.add_argument(
    "--funding-bar", action="store_true", help="Plot funding bars (projects in range)"
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
used_currencies = []
cur_fr = {}

ft_keys = ["income", "expenses", "taxes"]
manifest_fin_count = {
    "income": 0,
    "expenses": 0,
    "taxes": 0,
}

# limitation on commercial use isn't "free" ?
# just a flag for examination, not an argument to
# consider/reject the manifest
non_free_licenses = ["CC-BY-NC-SA-3.0", "commercial", "BSL"]
# licenses are user input, so we try to standardize a bit
# We standardise SPDX identifier on target side
# See https://spdx.org/licenses/preview/
lic_eq_map = {
    "Apache2": "Apache-2.0",
    "Apache V2": "Apache-2.0",
    "GPL-3.0 license": "GPL-3.0-or-later",
    "GPL-V2": "GPL-2.0-or-later",
    "unlicense": "Unlicense",
    "BSD-3": "BSD-3-Clause",
    "AGPL-3.0": "AGPL-3.0-or-later",
    "GPL-2.0": "AGPL-2.0-or-later",
    "GPL-3.0": "GPL-3.0-or-later",
    "LGPL-3.0": "LGPL-3.0-or-later",
}
# usage count for every tag used in projects
tag_count = {}

# multi-currency projects, an indicator of wider collaboration
mc_projects = []

# entity with the same name can submit multiple manifests.
# let's figure out who. It's a wide world, so names may match.
# Don't claim similarity, unless verified by other means
mdesc_by_ename = {}

# Map of project names to a "count"
# It's a wide world, so name clashes may happen. We'll use this
# to create a tag cloud
prj_map = {}

for idx, row in enumerate(reader):
    # Skip the header
    if idx == 0:
        continue

    nr += 1
    rid, url, created_at, updated_at, status, manifest_json = row

    if status != "active":
        print(status, url)
        disabled += 1
        continue

    try:
        manifest = json.loads(manifest_json)
        # print(json.dumps(manifest, indent=2))
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

    nfl = 0  # non-free-licenses
    mlic = {}
    for prj in manifest["projects"]:

        prj_name = prj["name"]
        if prj_name not in prj_map:
            prj_map[prj_name] = 1
        else:
            prj_map[prj_name] += 1

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

            # Replace with standardized value
            if lic in lic_eq_map:
                lic = lic_eq_map[lic]

            if lic in lic_map:
                lic_map[lic] += 1
            else:
                lic_map[lic] = 1
            if lic in non_free_licenses:
                nfl += 1
            if lic in mlic:
                mlic[lic] += 1
            else:
                mlic[lic] = 1

    this_mdesc["nfl"] = nfl
    this_mdesc["licences"] = mlic
    plan_max = {}
    manifest_currencies = []
    for plans in manifest["funding"]["plans"]:
        freq = plans["frequency"]
        currency = plans["currency"]
        cmult = currency_weight[currency] / currency_weight["USD"]
        if currency not in used_currencies:
            used_currencies.append(currency)
        if currency not in manifest_currencies:
            manifest_currencies.append(currency)
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
    this_mdesc["currencies"] = manifest_currencies

    mdesc.append(this_mdesc)

    ename = manifest["entity"]["name"]
    if ename not in mdesc_by_ename:
        mdesc_by_ename[ename] = []
    mdesc_by_ename[ename].append(this_mdesc)

    # Update stats
    npc = len(manifest_currencies)
    primary_cur = manifest_currencies[0]
    if primary_cur not in cur_fr:
        cur_fr[primary_cur] = 0
    if npc == 1:
        cur_fr[primary_cur] += max_fr
    elif npc > 1:
        mc_projects.append({"currencies": manifest_currencies, "mdesc": this_mdesc})
        print(
            f"WARNING: project id={rid} uses more than one currency({manifest_currencies}). Handle this. max_fr={max_fr}"
        )

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
            currency = hist["currency"]
            if currency not in used_currencies:
                used_currencies.append(currency)
            c_weight = (
                currency_weight[currency] / currency_weight["USD"]
            )  # required field
            for key in ft_keys:
                if key in hist:
                    value = hist[key] * c_weight
                    annual_fin_totals[year][key] += value
                    fin_totals[key] += value
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

mdn = copy.copy(mdesc_by_ename)
for ename in mdesc_by_ename:
    mdesc_list = mdesc_by_ename[ename]
    if len(mdesc_list) == 1:
        mdn.pop(ename)
mdesc_by_ename = mdn

# list of funding requests, clipped to the range (10-100k)
# source : https://www.rapidtables.com/web/color/purple-color.html
b1_color = "#E6E6FA"  # 0.  lavender
cmap = [
    "#D8BFD8",  # 10.   thistle
    "#DDA0DD",  # 20.  plum
    "#EE82EE",  # 30.  violet
    "#DA70D6",  # 40.  orchid
    "#BA55D3",  # 50.  medium orchid
    "#8A2BE2",  # 60.  blue violet
    "#9932CC",  # 70.  dark orchid
    "#8B008B",  # 80.  dark magenta
    "#800080",  # 90.  Purple
    "#4B0082",  # 100. Indigo
]


def val2color(fr):
    idx = ((fr - ft) / (fmax - ft)) * (len(cmap) - 1)
    idx = math.floor(idx)
    return cmap[idx]


clipped_colors = []
ety_clipped_funding = []
fr_below_ft = []
ety_clipped_sum = 0
for minfo in mdesc:
    max_fr = minfo["funding-plan-max"]["max-fr"]
    if max_fr >= ft:
        max_fr = min(max_fr, fmax)
        ety_clipped_funding.append(max_fr)
    elif max_fr > 0:
        # accumulate values below 10k in one bucket
        fr_below_ft.append(max_fr)
        # we ignore 0 as we can't meaningfully process it
        # here
    ety_clipped_sum += max_fr

ety_clipped_funding.sort()
ety_clipped_colors = [val2color(x) for x in ety_clipped_funding]

# bucket1 = statistics.mean(fr_below_ft)
print("Entities below lower threshold = ", len(fr_below_ft))
bucket1 = sum(fr_below_ft)
ety_clipped_funding.insert(0, bucket1)
ety_clipped_colors.insert(0, b1_color)

# Highest funding requirements float to the top!
mdesc.sort(key=lambda x: x["funding-plan-max"]["max-fr"], reverse=True)

print("==============================================================")
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
used_currencies.sort()
print("Currencies:", used_currencies)
print()
print("Cumulative funding requested, by currency, in USD:")
pprint(cur_fr)
print("Multi-currency projects:")
for mcp in mc_projects:
    emdesc = mcp["mdesc"]
    url = emdesc["url"]
    manifest = emdesc["manifest"]
    ename = manifest["entity"]["name"]
    max_fr = math.floor(emdesc["funding-plan-max"]["max-fr"])
    print(f"  {mcp['currencies']} {url} {ename} {max_fr}")
print("Entities with more than 1 project:")
for ename in mdesc_by_ename:
    print(f"  {ename}")
    for emdesc in mdesc_by_ename[ename]:
        url = emdesc["url"]
        print(f"    {url}")
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
    if minfo["nfl"] > 0:
        print("  Non-free licences: ", minfo["nfl"])
    print("  Licenses : ", minfo["licences"])
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
    d_currencies = []
    return (
        d_manifests,
        d_projects,
        d_etype,
        d_fin_totals,
        d_manifests_above_ft,
        d_mfr_total,
        d_currencies,
    )


(
    c_manifests,
    c_projects,
    c_etype,
    c_fin_totals,
    c_manifests_above_ft,
    c_mfr_total,
    c_currencies,
) = reset_counters()
(
    d_manifests,
    d_projects,
    d_etype,
    d_fin_totals,
    d_manifests_above_ft,
    d_mfr_total,
    d_currencies,
) = reset_counters()

# We'll save a timeseries for plotting
timeseries = {
    "t": [],  # day since launch
    "d_manifests": [],
    "d_projects": [],
    "d_mfr_total": [],
    "d_etype": [],
    "d_manifests_above_ft": [],
    "d_fin_totals": [],
    "d_currencies": [],
    "c_manifests": [],
    "c_projects": [],
    "c_mfr_total": [],
    "c_etype": [],
    "c_manifests_above_ft": [],
    "c_fin_totals": [],
    "c_currencies": [],
}

print("=========================================================")
print("Trends from T=0...")
print("=========================================================")
for idx, minfo in enumerate(mdesc):
    tdiff = minfo["created_at"] - launch_dt
    if (tdiff.days > day_since_launch) or (idx == len(mdesc) - 1):
        c_manifests += d_manifests
        c_projects += d_projects
        c_mfr_total += d_mfr_total
        c_mfr_total = math.floor(c_mfr_total)
        d_mfr_total = math.floor(d_mfr_total)
        d_currencies.sort()
        for currency in d_currencies:
            if currency not in c_currencies:
                c_currencies.append(currency)
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
        timeseries["d_currencies"].append(d_currencies)
        timeseries["c_manifests"].append(copy.copy(c_manifests))
        timeseries["c_projects"].append(copy.copy(c_projects))
        timeseries["c_mfr_total"].append(copy.copy(c_mfr_total))
        timeseries["c_etype"].append(copy.copy(c_etype))
        timeseries["c_manifests_above_ft"].append(c_manifests_above_ft)
        timeseries["c_fin_totals"].append(c_fin_totals)
        timeseries["c_currencies"].append(c_currencies)
        # dump cumulative stats
        print(f"Day {day_since_launch}:")
        print("  New manifests:", d_manifests)
        print("  New projects:", d_projects)
        print("  New entity types:", d_etype)
        print("  Manifests > funding threshold:", d_manifests_above_ft)
        print("  Funding requested :", d_mfr_total)
        print("  Additional financials:", d_fin_totals)
        print("  Currencies used:", d_currencies)
        print("  Cumulative:")
        print("    Manifests:", c_manifests)
        print("    Projects:", c_projects)
        print("    Entity types:", c_etype)
        print("    Manifests > funding threshold:", c_manifests_above_ft)
        print("    Funding requested :", c_mfr_total)
        print("    Financials:", c_fin_totals)
        print("    Currencies used:", c_currencies)
        (
            d_manifests,
            d_projects,
            d_etype,
            d_fin_totals,
            d_manifests_above_ft,
            d_mfr_total,
            d_currencies,
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
    for plans in manifest["funding"]["plans"]:
        currency = plans["currency"]
        if currency not in d_currencies:
            d_currencies.append(currency)
    if "history" in manifest["funding"] and manifest["funding"]["history"]:
        for hist in manifest["funding"]["history"]:
            currency = hist["currency"]
            if currency not in d_currencies:
                d_currencies.append(currency)
# fill holes in the timeseries. Not on every day may new manifests be submitted.
# On a day where d_ values don't change, they must be set to 0
ts2 = copy.deepcopy(timeseries)
inaction_days = 0
for idx, (start, end) in enumerate(zip(timeseries["t"][:-1], timeseries["t"][1:])):
    if end > start + 1:
        # we have no action for one or more days
        # print(start, end)
        for di in range(end - start - 1):
            inaction_days += 1
            this_idx = start + di + 1
            ts2["t"].insert(this_idx, this_idx)
            for key in [
                "manifests",
                "projects",
                "mfr_total",
                "etype",
                "manifests_above_ft",
                "fin_totals",
                "currencies",
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
                d_currencies,
            ) = reset_counters()
            ts2["d_manifests"].insert(this_idx, d_manifests)
            ts2["d_projects"].insert(this_idx, d_projects)
            ts2["d_etype"].insert(this_idx, d_etype)
            ts2["d_fin_totals"].insert(this_idx, d_fin_totals)
            ts2["d_manifests_above_ft"].insert(this_idx, d_manifests_above_ft)
            ts2["d_mfr_total"].insert(this_idx, d_mfr_total)
            ts2["d_currencies"].insert(this_idx, d_currencies)

print("Days where no entities joined in the action:", inaction_days)

# Done expanding, so rename
timeseries = ts2
del ts2
# pprint(timeseries)

# Show info for tags.
# project-tags.txt is a copy of https://floss.fund/static/project-tags.txt
known_tags = [x.strip() for x in open("project-tags.txt", "r").readlines()]
used_tags = list(tag_count.keys())
unused_tags = {}
for tag in known_tags:
    if tag not in used_tags:
        unused_tags[tag] = 1
tc_list = list(zip(tag_count.keys(), tag_count.values()))
tc_list.sort(key=lambda x: x[1], reverse=True)
print("Used tags, and their frequencies are:")
pprint(tc_list)
print("These tags (suggested by floss.fund) are NOT used by any project:")
pprint(unused_tags)

# Generate word cloud with tags
if args.word_cloud:
    # One with the floss flower mask
    floss_mask = np.array(Image.open("images/mask-floss-fund-logo.png"))
    wc = wordcloud.WordCloud(
        background_color="white",
        mask=floss_mask,
        contour_width=5,
        contour_color="#2ea650",
    )
    wc.fit_words(tag_count)
    wc.to_file("floss_fund_tags.png")

    # One for "unused" tags. These all have count=1
    wc2 = wordcloud.WordCloud(background_color="white", width=400, height=400)
    wc2.fit_words(unused_tags)
    wc2.to_file("unused_tags.png")

    # One for "unused" tags. These all have count=1
    print("No of projects = ", len(prj_map))
    wc3 = wordcloud.WordCloud(background_color="white", width=1920, height=1280)
    wc3.fit_words(prj_map)
    wc3.to_file("floss_projects.png")

# Pie chart
if args.funding_pie:
    labels = cur_fr.keys()
    sizes = cur_fr.values()
    explode = [
        0.1 if currency == "USD" else 0 for currency in labels
    ]  # only "explode" USD

    fig1, ax1 = plt.subplots()
    ax1.pie(
        sizes,
        explode=explode,
        labels=labels,
        autopct="%1.1f%%",
        shadow=True,
        startangle=90,
    )
    ax1.axis("equal")  # Equal aspect ratio ensures that pie is drawn as a circle.
    plt.show()

# Bar + line plot
if args.funding_trend:
    p1_t = pd.DataFrame(
        {
            "d_manifests": timeseries["d_manifests"],
            "d_projects": timeseries["d_projects"],
            "c_mfr_total": timeseries["c_mfr_total"],
        }
    )

    # p1_t[['d_manifests', 'd_projects']].plot(kind='bar')
    p1_t[["d_manifests"]].plot(kind="bar")
    p1_t["c_mfr_total"].plot(secondary_y=True, color="red")
    plt.show()

# Bar plot
if args.funding_bar:
    fund_sum = 0
    for idx, val in enumerate(ety_clipped_funding):
        percentage = math.floor((fund_sum / ety_clipped_sum) * 100)
        print(idx, val, 100 - percentage)
        fund_sum += val
    print(ety_clipped_sum)
    # Area plot
    y = ety_clipped_funding
    x = range(len(y))
    plt.bar(x, y, color=ety_clipped_colors)
    plt.show()
