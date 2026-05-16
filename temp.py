import pandas as pd
import numpy as np

# Define boundaries
lat_start = 11.33900
lat_end = 11.33930
lon_start = 77.71950
lon_end = 77.72050

lat_step = 0.00002
lon_step = 0.00010

points = []

lat = lat_start
direction = 1  # 1 = forward, -1 = reverse

timestamp = pd.Timestamp("2026-03-03 15:00:00")

while lat <= lat_end:
    if direction == 1:
        lon_range = list(np.arange(lon_start, lon_end, lon_step))
    else:
        lon_range = list(np.arange(lon_end, lon_start, -lon_step))

    for lon in lon_range:
        points.append([
            timestamp,
            round(lat, 6),
            round(lon, 6),
            1.2,
            11.0
        ])
        timestamp += pd.Timedelta(seconds=0.5)

    lat += lat_step
    direction *= -1  # reverse direction each row

df = pd.DataFrame(points, columns=["Timestamp","Latitude","Longitude","Altitude","Speed"])

df.to_csv("zigzag_path.csv", index=False)