#
# streamlit application to visualize FLOSS/fund
# over the web
#
# Gets data directly from dir.floss.fund
#
# Thanks to Ansh Arora for the idea of using streamlit to do this.
# He made this : https://github.com/ansharora28/floss-fund-analysis
# effectively showing me how easy that is to do with streamlit.
#
import streamlit as st
import pandas as pd
import numpy as np
import tarfile
import requests
import io
import stats
import matplotlib.pyplot as plt
import math

# See shortcode list here
# https://streamlit-emoji-shortcodes-streamlit-app-gwckff.streamlit.app/
st.set_page_config(
    page_title="Overall Status",
    page_icon=":chart_with_upwards_trend:",
)

# Get the manifest and extract it in memory
# FIXME use streamlit's cache system later
manifest_tgz = "https://dir.floss.fund/funding-manifests.tar.gz"
rg = requests.get(manifest_tgz)
mzip = tarfile.open(fileobj=io.BytesIO(rg.content), mode="r:gz")
manifest_bytes = mzip.extractfile("funding-manifests.csv").read()

# Process the manifest
info, timeseries = stats.process_csv(io.StringIO(manifest_bytes.decode("utf-8")))

# Funding trend visualization
# bar overlaid with line
p1_t = pd.DataFrame(
    {
        "New Entities": timeseries["d_manifests"],
        "d_projects": timeseries["d_projects"],
        "c_mfr_total_clipped": timeseries["c_mfr_total_clipped"],
    }
)
plt1 = p1_t[["New Entities"]].plot(kind="bar")
plt2 = p1_t["c_mfr_total_clipped"].plot(secondary_y=True, color="red")
days_since_launch = len(timeseries["d_manifests"])
ticks = list(range(0, days_since_launch, 1))
tick_label = []
# generic auto-ticks based on number of days, it's kept a multiple of 5
tick_interval = (((days_since_launch/10)+4)//5)*5
for val in ticks:
    if val % tick_interval == 0:
        tick_label.append(str(val))
    else:
        tick_label.append("")
plt.xticks(ticks, tick_label)
plt1.set_xlabel("Days since fund launch")
plt1.set_ylabel("Entities")
plt2.set_ylabel("Funds Requested (Million USD)")

st.title("FLOSS/fund at a glance")
st.write(
    """
[FLOSS/fund](https://floss.fund/) is a 1 million USD global fund for FLOSS projects.
It has been accepting applications since 15th October, 2024. Graph below shows how new
entities(org, individual, group) are applying on a daily basis, and the trend of the
cumulative funding requested over time.
"""
)
st.pyplot(plt)
st.write(
    """
%d individuals, %d organizations, %d groups have applied for funding.
This is a cumulative **%d entities** representing **%d projects**, asking for
**%1.2f Million USD** in funding. Days with no blue bars indicate that no new
applications were received on that day. There have been %d such days, out of
%d days that the fund has been active.
"""
    % (
        info.etype_count["individual"],
        info.etype_count["organisation"],
        info.etype_count["group"],
        timeseries["c_manifests"][-1],
        timeseries["c_projects"][-1],
        (timeseries["c_mfr_total_clipped"][-1] // 1e4) / 100.0,
        info.inaction_days,
        days_since_launch,
    )
)

#st.write('''
#FLOSS/fund provides in the range of 10k-100k USD per entity.
#The spread of amount of funds requested by entities is shown in the graph below.
#Entities that request less than 10k USD have been merged into
#the first bucket. Rest are individual entities.
#''')
#fund_sum = 0
#for idx, val in enumerate(info.ety_clipped_funding):
#    percentage = math.floor((fund_sum / info.ety_clipped_sum) * 100)
#    print(idx, val, 100 - percentage)
#    fund_sum += val
#y = info.ety_clipped_funding
#x = range(len(y))
#fig2, ax2 = plt.subplots()
#ax2.bar(x, y, color=info.ety_clipped_colors)
#ax2.set_ylabel("Funding requested (USD)")
#ax2.set_xlabel("Maximum funding requested by entities (sorted)")
#ax2.set_xticks([])
#st.pyplot(fig2)

st.write('''
FLOSS/fund provides in the range of 10k-100k USD per entity.
Several projects have funding plans that are less than 10k.
Graph below shows how many entities fall in specific funding request
ranges. Complete details of all entities are at the end of this page.
''')
range_occurences = []
hist_labels = ['< 10k USD']
range_occurences.append(len(info.fr_below_ft))
min_val = 10*1000 - 1 # achieves >= in the filter logic, see below
for max_val in range(20*1000, 100*1000+1, 10*1000):
    count = len(list(filter(lambda x: ((x>min_val) and x<=max_val), info.ety_clipped_funding[1:])))
    range_occurences.append(count)
    hist_labels.append("%sk - %sk USD"%(min_val//1000, max_val//1000))
    min_val = max_val
fig3, ax3 = plt.subplots()
ax3.barh(hist_labels, range_occurences)
ax3.set_xlabel("Number of entities")
st.pyplot(fig3)

st.write('''
FLOSS/fund is accepting projects. If you know any projects, please refer FLOSS/fund
to them.  Community and individual outreach can help more projects get the funds
they need.
''')
# st.divider()

st.write(
    """
Note that funds may be requested in any currency. Here is the spread of funds requested,
by currency:
"""
)
labels = info.cur_fr.keys()
sizes = info.cur_fr.values()
explode = [0.1 if currency == "USD" else 0 for currency in labels]  # only "explode" USD
fig1, ax1 = plt.subplots()
ax1.pie(
    sizes,
    explode=explode,
    labels=labels,
    autopct="%1.1f%%",
    shadow=True,
    # startangle=st_angle,
    textprops={"fontsize": 6},
)
ax1.axis("equal")  # Equal aspect ratio ensures that pie is drawn as a circle.
st.pyplot(fig1)

fc_freq = {}
for minfo in info.mdesc:
    fc_names = minfo['funding_channel_names']
    for t in fc_names:
        if t in fc_freq:
            fc_freq[t] += 1
        else:
            fc_freq[t] = 1
# Don't show for now
#st.write(fc_freq)

# Highest funding requirements float to the top!
info.mdesc.sort(key=lambda x: x["funding-plan-max"]["max-fr"], reverse=True)
freq = []
freq_ename = []
for minfo in info.mdesc:
    mf = minfo["funding-plan-max"]["max-fr"]
    freq.append(math.floor(mf))
    manifest = minfo["manifest"]
    freq_ename.append(manifest["entity"]["name"])

st.divider()
st.subheader('Details of Entities')
df = pd.DataFrame({"Entity Name": freq_ename, "Max Funding Requested (USD)": freq})
st.write('''
Table below lists all entities, and funding requested by them. Note that the list
is sorted such that entities that have requested the maximum funds are on top.
The largest funding plan for each entity is considered. Note that funding plans
asking for more than 100k have been clipped to 100k in all the data prior to this,
but here we show everything as is. Please scroll the list to see all the entries.
''')
df

if len(info.disabled_mdesc)>0:
    st.subheader('Disabled Manifests')
    st.markdown('''
FLOSS/fund internally implements a crawler that periodically updates
manifests from their live location. If a manifest is inaccessible or
invalid, it is disabled. There are %s disabled entities. These are:
'''%(len(info.disabled_mdesc)))
    mnames = []
    for minfo in info.disabled_mdesc:
        manifest = minfo["manifest"]
        mnames.append(manifest["entity"]["name"])
    st.dataframe({"Entity Name": mnames}, use_container_width=True)
st.subheader('Project Info')
st.markdown('''
Details of this project are on
[its github page](https://github.com/shreekumar3d/floss-fund-envelope/).

[Ansh Arora](https://ansharora.in/) came up with the idea of a live status view,
and hacked up an
[app to visualize the FLOSS/fund](https://floss-fund.streamlit.app/) in quick time.
This started off from there, and includes some of his ideas as well.
''')
