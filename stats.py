#!/usr/bin/env python3
#
# stats
#
# Extract useful stats from funding-manifest.csv file
#
# Not elegant but does what needs to be done - basically
# a bunch of calculations (spreadsheet style stuff)
# in code. Everything is returned from process_csv
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
from PIL import Image
import numpy as np
import statistics

# FLOSS fund is looking to fund entities in the range
# 10k - 100k.
ft = 10 * 1000  # 10k USD min
fmax = 100 * 1000

# Currency conversion as of 26 Nov 2024
# This isn't correct either for the past, or for
# the future, but it's a good enough approximation for now
# FIXME: fix this soon
currency_weight = {
    "USD": 84.31,
    "EUR": 88.59,
    "CAD": 59.76,
    "GBP": 105.82,
    "ZAR": 84.31/19.46990, # as on 9 Apr 2025.
    "AUD": 56.61, # as on Aug 19 2025
    "MXN": 4.64, # as on Aug 19 2025
    "INR": 1,
}


def fund_clip(val):
    if val < ft:
        return ft
    if val > fmax:
        return fmax
    return val

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

ft_keys = ["income", "expenses", "taxes"]
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
    "gplV3": "GPL-3.0-or-later",
    "LGPL-3.0": "LGPL-3.0-or-later",
}


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
    d_mfr_total_clipped = 0
    d_currencies = []
    return (
        d_manifests,
        d_projects,
        d_etype,
        d_fin_totals,
        d_manifests_above_ft,
        d_mfr_total,
        d_mfr_total_clipped,
        d_currencies,
    )


def process_csv(csvfile):
    # FIXME ugliness in this script has to do with streamlit.
    # it doesn't seem to delete globals. We'll clean this up
    # in due time!
    nr = 0
    nad = 0
    last_entity_dt = 0
    disabled = 0
    errors = 0
    mdesc = []
    disabled_mdesc = []
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
    unused_tags = {}
    tc_list = None
    manifest_fin_count = {
        "income": 0,
        "expenses": 0,
        "taxes": 0,
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
    fin_totals = {
        "income": 0,
        "expenses": 0,
        "taxes": 0,
    }
    ety_clipped_funding = []
    fr_below_ft = []
    ety_clipped_sum = 0
    inaction_days = 0

    reader = csv.reader(csvfile)
    for idx, row in enumerate(reader):
        # Skip the header and the localhost test line
        if idx <= 1:
            continue

        nr += 1
        rid, url, created_at, updated_at, status, manifest_json = row

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

        # FLOSS/fund deos not consider disabled manifests, so remove them now
        # Don't process further if not active
        if status != "active":
            print(status, url)
            disabled += 1
            disabled_mdesc.append(this_mdesc)
            continue

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
        funding_channel_types = []
        for channels in manifest["funding"]["channels"]:
            funding_channel_types.append(channels['guid'])
        this_mdesc["funding_channel_names"] = funding_channel_types
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
            # print(
            #    f"WARNING: project id={rid} uses more than one currency({manifest_currencies}). Handle this. max_fr={max_fr}"
            # )

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

    # Highest funding requirements float to the top!
    mdesc.sort(key=lambda x: x["funding-plan-max"]["max-fr"], reverse=True)
    bucket1 = sum(fr_below_ft)
    ety_clipped_funding.insert(0, bucket1)
    ety_clipped_colors.insert(0, b1_color)

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

    (
        c_manifests,
        c_projects,
        c_etype,
        c_fin_totals,
        c_manifests_above_ft,
        c_mfr_total,
        c_mfr_total_clipped,
        c_currencies,
    ) = reset_counters()
    (
        d_manifests,
        d_projects,
        d_etype,
        d_fin_totals,
        d_manifests_above_ft,
        d_mfr_total,
        d_mfr_total_clipped,
        d_currencies,
    ) = reset_counters()

    # We'll save a timeseries for plotting
    timeseries = {
        "t": [],  # day since launch
        "d_manifests": [],
        "d_projects": [],
        "d_mfr_total": [],
        "d_mfr_total_clipped": [],
        "d_etype": [],
        "d_manifests_above_ft": [],
        "d_fin_totals": [],
        "d_currencies": [],
        "c_manifests": [],
        "c_projects": [],
        "c_mfr_total": [],
        "c_mfr_total_clipped": [],
        "c_etype": [],
        "c_manifests_above_ft": [],
        "c_fin_totals": [],
        "c_currencies": [],
    }

    for idx, minfo in enumerate(mdesc):
        tdiff = minfo["created_at"] - launch_dt
        if (tdiff.days > day_since_launch) or (idx == len(mdesc) - 1):
            c_manifests += d_manifests
            c_projects += d_projects
            c_mfr_total += d_mfr_total
            c_mfr_total_clipped += d_mfr_total_clipped
            c_mfr_total = math.floor(c_mfr_total)
            c_mfr_total_clipped = math.floor(c_mfr_total_clipped)
            d_mfr_total = math.floor(d_mfr_total)
            d_mfr_total_clipped = math.floor(d_mfr_total_clipped)
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
            timeseries["d_mfr_total_clipped"].append(copy.copy(d_mfr_total_clipped))
            timeseries["d_etype"].append(copy.copy(d_etype))
            timeseries["d_manifests_above_ft"].append(d_manifests_above_ft)
            timeseries["d_fin_totals"].append(d_fin_totals)
            timeseries["d_currencies"].append(d_currencies)
            timeseries["c_manifests"].append(copy.copy(c_manifests))
            timeseries["c_projects"].append(copy.copy(c_projects))
            timeseries["c_mfr_total"].append(copy.copy(c_mfr_total))
            timeseries["c_mfr_total_clipped"].append(copy.copy(c_mfr_total_clipped))
            timeseries["c_etype"].append(copy.copy(c_etype))
            timeseries["c_manifests_above_ft"].append(c_manifests_above_ft)
            timeseries["c_fin_totals"].append(c_fin_totals)
            timeseries["c_currencies"].append(c_currencies)
            (
                d_manifests,
                d_projects,
                d_etype,
                d_fin_totals,
                d_manifests_above_ft,
                d_mfr_total,
                d_mfr_total_clipped,
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
        d_mfr_total_clipped += fund_clip(minfo["funding-plan-max"]["max-fr"])
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
                    "mfr_total_clipped",
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
                    d_mfr_total_clipped,
                    d_currencies,
                ) = reset_counters()
                ts2["d_manifests"].insert(this_idx, d_manifests)
                ts2["d_projects"].insert(this_idx, d_projects)
                ts2["d_etype"].insert(this_idx, d_etype)
                ts2["d_fin_totals"].insert(this_idx, d_fin_totals)
                ts2["d_manifests_above_ft"].insert(this_idx, d_manifests_above_ft)
                ts2["d_mfr_total"].insert(this_idx, d_mfr_total)
                ts2["d_mfr_total_clipped"].insert(this_idx, d_mfr_total_clipped)
                ts2["d_currencies"].insert(this_idx, d_currencies)

    last_entity_dt = launch_dt + datetime.timedelta(timeseries["t"][-1])
    nad = datetime.datetime.now(datetime.UTC) - last_entity_dt
    # Insert zeros at the end of the arrays - corresponding to
    # trailing days that did not see any new entity joining
    for idx in range(nad.days):
        ts2["t"].append(timeseries["t"][-1])
        for key in [
            "manifests",
            "projects",
            "mfr_total",
            "mfr_total_clipped",
            "etype",
            "manifests_above_ft",
            "fin_totals",
            "currencies",
        ]:
            key_name = f"c_{key}"
            ts2[key_name].append(timeseries[key_name][-1])
        (
            d_manifests,
            d_projects,
            d_etype,
            d_fin_totals,
            d_manifests_above_ft,
            d_mfr_total,
            d_mfr_total_clipped,
            d_currencies,
        ) = reset_counters()
        ts2["d_manifests"].append(d_manifests)
        ts2["d_projects"].append(d_projects)
        ts2["d_etype"].append(d_etype)
        ts2["d_fin_totals"].append(d_fin_totals)
        ts2["d_manifests_above_ft"].append(d_manifests_above_ft)
        ts2["d_mfr_total"].append(d_mfr_total)
        ts2["d_mfr_total_clipped"].append(d_mfr_total_clipped)
        ts2["d_currencies"].append(d_currencies)

    # Done expanding, so rename
    timeseries = ts2
    del ts2
    # pprint(timeseries)

    # Compute info for tags.
    # project-tags.txt is a copy of https://floss.fund/static/project-tags.txt
    known_tags = [x.strip() for x in open("project-tags.txt", "r").readlines()]
    used_tags = list(tag_count.keys())
    unused_tags = {}
    for tag in known_tags:
        if tag not in used_tags:
            unused_tags[tag] = 1
    tc_list = list(zip(tag_count.keys(), tag_count.values()))
    tc_list.sort(key=lambda x: x[1], reverse=True)

    class Info:
        pass

    info = Info()
    info.nr = nr
    info.nad = nad
    info.last_entity_dt = last_entity_dt
    info.disabled = disabled
    info.errors = errors
    info.mdesc = mdesc
    info.disabled_mdesc = disabled_mdesc
    info.meets_ft = meets_ft
    info.manifests_zfr = manifests_zfr
    info.etype_count = etype_count
    info.etype_meets_ft = etype_meets_ft
    info.erole_count = erole_count
    info.etype_proj_count = etype_proj_count
    info.etype_max_fr = etype_max_fr
    info.lic_map = lic_map
    info.annual_fin_totals = annual_fin_totals
    info.used_currencies = used_currencies
    info.cur_fr = cur_fr
    info.unused_tags = unused_tags
    info.tc_list = tc_list
    info.manifest_fin_count = manifest_fin_count
    info.tag_count = tag_count
    info.mc_projects = mc_projects
    info.mdesc_by_ename = mdesc_by_ename
    info.prj_map = prj_map
    info.fin_totals = fin_totals
    info.ety_clipped_funding = ety_clipped_funding
    info.ety_clipped_colors = ety_clipped_colors
    info.fr_below_ft = fr_below_ft
    info.ety_clipped_sum = ety_clipped_sum
    info.inaction_days = inaction_days

    return info, timeseries
