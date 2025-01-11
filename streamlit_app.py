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
for val in ticks:
    if val % 5 == 0:
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
This is a cumulative %d entities representing %d projects, asking for
%1.2f Million USD.

Days with no blue bars indicate that no new applications were received on that day.
There have been %d such days, out of %d days that the fund has been active.

FLOSS/fund is accepting projects. If you know any projects, please refer FLOSS/fund
to them.  Community and individual outreach can help more projects get the funds
they need.
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
