#!/usr/bin/env python3
#
# Refactored stuff from fm-stats.py
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
# 3. Run this tool : ./manifest-show.py data/funding-manifests.csv
#
# To generate plots and charts, checkout args using --help or below.
# Note that there is an element of randomness in the word clouds.
#
import argparse
import stats
from pprint import pprint
import math
import pandas as pd
import matplotlib.pyplot as plt


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
info, timeseries = stats.process_csv(csvfile)


def dump_stats():
    print("==============================================================")
    print(
        f"Total manifests = {info.nr} Disabled = {info.disabled} Errors = {info.errors}"
    )
    print(f"Manifests above funding threshold = {info.meets_ft}")
    print(f"Manifests requesting NO SPECIFIC (0) funding = {info.manifests_zfr}")
    print("Cumulative financials for all years reported in manifests:")
    pprint(info.fin_totals)
    print("Entity Role:")
    print(info.erole_count)
    print("Entity Type:")
    print(info.etype_count)
    print("Projects per Entity Type:")
    print(info.etype_proj_count)
    print("Requested Max funding per Entity Type:")
    print(info.etype_max_fr)
    print("Above threshold manifests per Entity Type:")
    print(info.etype_meets_ft)
    print("Licenses:")
    pprint(info.lic_map)
    print("Annual Financial Totals:")
    pprint(info.annual_fin_totals)
    print("Finances Reported by entities:")
    pprint(info.manifest_fin_count)
    info.used_currencies.sort()
    print("Currencies:", info.used_currencies)
    print()
    print("Cumulative funding requested, by currency, in USD:")
    pprint(info.cur_fr)
    print("Multi-currency projects:")
    for mcp in info.mc_projects:
        emdesc = mcp["mdesc"]
        url = emdesc["url"]
        manifest = emdesc["manifest"]
        ename = manifest["entity"]["name"]
        max_fr = math.floor(emdesc["funding-plan-max"]["max-fr"])
        print(f"  {mcp['currencies']} {url} {ename} {max_fr}")
    print("Entities with more than 1 funding request(manifest):")
    for ename in info.mdesc_by_ename:
        print(f"  {ename}")
        for emdesc in info.mdesc_by_ename[ename]:
            url = emdesc["url"]
            print(f"    {url}")
    print()
    print(
        f"-- {info.meets_ft} manifests above funding threshold {stats.ft//1000}k USD --"
    )
    print()
    for idx, minfo in enumerate(info.mdesc):
        if idx == info.meets_ft:
            print()
            print(f"-- Manifests below funding threshold {stats.ft//1000}k USD --")
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
    print("Entities below lower threshold = ", len(info.fr_below_ft))


def dump_trends():
    print("=========================================================")
    print("Trends from T=0...")
    print("=========================================================")
    print("No entity joined for the last :", info.nad)
    print("Days where no entities joined in the action:", info.inaction_days)
    print("Last entity joined at :", info.last_entity_dt)
    #            # dump cumulative stats
    #            print(
    #                f"Day {day_since_launch}:",
    #                launch_dt + datetime.timedelta(days=day_since_launch),
    #            )
    #            print("  New manifests:", d_manifests)
    #            print("  New projects:", d_projects)
    #            print("  New entity types:", d_etype)
    #            print("  Manifests > funding threshold:", d_manifests_above_ft)
    #            print("  Funding requested :", d_mfr_total)
    #            print("  Funding requested (clipped) :", d_mfr_total_clipped)
    #            print("  Additional financials:", d_fin_totals)
    #            print("  Currencies used:", d_currencies)
    #            print("  Cumulative:")
    #            print("    Manifests:", c_manifests)
    #            print("    Projects:", c_projects)
    #            print("    Entity types:", c_etype)
    #            print("    Manifests > funding threshold:", c_manifests_above_ft)
    #            print("    Funding requested :", c_mfr_total)
    #            print("    Funding requested (clipped) :", c_mfr_total_clipped)
    #            print("    Financials:", c_fin_totals)
    #            print("    Currencies used:", c_currencies)
    print("Used tags, and their frequencies are:")
    pprint(info.tc_list)
    print("These tags (suggested by floss.fund) are NOT used by any project:")
    pprint(info.unused_tags)


dump_stats()
# dump_trends()

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


# bucket1 = statistics.mean(fr_below_ft)
# bucket1 = sum(info.fr_below_ft)
# ety_clipped_funding.insert(0, bucket1)
# ety_clipped_colors.insert(0, b1_color)

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
            "c_mfr_total_clipped": timeseries["c_mfr_total_clipped"],
        }
    )

    # p1_t[['d_manifests', 'd_projects']].plot(kind='bar')
    p1_t[["d_manifests"]].plot(kind="bar")
    p1_t["c_mfr_total_clipped"].plot(secondary_y=True, color="red")
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
