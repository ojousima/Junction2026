

import requests
import pandas as pd
import matplotlib.pyplot as plt

base = "https://heatpumpmonitor.org"

params = {
    "id": 2,
    "feeds": "heatpump_outsideT,heatpump_flowT,heatpump_returnT",
    "start": "01-02-2025",
    "end": "02-02-2025",
    "interval": 60,
    "average": 1,
    "timeformat": "notime",
}

r = requests.get(
    base + "/timeseries/data",
    params=params,
    timeout=30
)
r.raise_for_status()

data = r.json()
print("Response sample:", str(data)[:500])
