#
# streamlit application to visualize FLOSS/fund
# over the web
#
# Gets data directly from dir.floss.fund
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
FLOSS/fund is accepting applications since 15th October, 2024.
This graph shows how new entities(org, individual, group) are applying on a daily basis,
and the trend of the cumulative funding requested over time.
"""
)
st.pyplot(plt)
st.write(
    """
Days with no blue bars indicate that no new applications were received on that day.
There have been %d such days, out of %d days that the fund has been active.
"""
    % (info.inaction_days, days_since_launch)
)
