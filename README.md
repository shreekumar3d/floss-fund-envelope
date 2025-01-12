# floss-funding-envelope

This project collects and analyses funding related data from
[FLOSS/fund](https://dir.floss.fund/), which is provided as a daily dump of funding manifests.

This project includes two useful tools:

  * An online [live status view](https://floss-fund-live-status.streamlit.app/), built using [streamlit](https://streamlit.io/) : streamlit_app.py
  * A command line tool, fm-stats.py, that dumps info about manifests, and generates some graphs. This tool was initially built to understand various aspects of applicants to the fund. It was first used to generate data and graphs for [this article](https://techbitsatoms.substack.com/p/analyzing-the-flossfund-database).

## Thanks to

[Ansh Arora](https://ansharora.in/) hacked up a [app to visualize the FLOSS/fund](https://floss-fund.streamlit.app/) in quick time. I used that as the basis to build the live status view.