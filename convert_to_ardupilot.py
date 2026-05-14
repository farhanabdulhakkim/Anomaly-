"""
convert_to_ardupilot.py
Converts drone_flight_with_timestamp.xls into ArduPilot CSV log format
so logparser.py can parse it.

ArduPilot CSV column layout:
  col 0  = line counter
  col 1  = wall-clock timestamp
  col 2  = message type (GPS or ATT)
  col 3+ = payload fields (positional)

GPS payload positions (3-based):
  [3]=TimeUS [4]=Status [5]=GMS [6]=GWk [7]=NSats [8]=HDop [9]=HAcc
  [10]=Lat   [11]=Lng   [12]=Alt [13]=Spd

ATT payload positions (3-based):
  [3]=TimeUS [4]=DesRoll [5]=Roll [6]=DesPitch [7]=Pitch [8]=DesYaw [9]=Yaw
"""

import random
import pandas as pd

random.seed(42)

df = pd.read_csv("drone_flight_with_timestamp.xls")
df.columns = [c.strip() for c in df.columns]

rows = []
counter = 0

for _, r in df.iterrows():
    ts  = str(r["Timestamp"])
    lat = r["Latitude"]
    lon = r["Longitude"]
    alt = r["Altitude"]
    spd = r["Speed"]

    # GPS row (16 columns total)
    rows.append([
        counter, ts, "GPS",
        counter * 1000,   # TimeUS
        3,                # Status (3 = 3D fix)
        0, 0,             # GMS, GWk
        10,               # NSats
        1.2, 0.5,         # HDop, HAcc
        lat, lon, alt, spd,
        0, 0,             # VZ, U
    ])
    counter += 1

    # ATT row (12 columns total, padded to 16 with empty strings)
    roll  = round(random.uniform(-5, 5), 4)
    pitch = round(random.uniform(-5, 5), 4)
    yaw   = round(random.uniform(0, 360), 4)
    rows.append([
        counter, ts, "ATT",
        counter * 1000,   # TimeUS
        0,                # DesRoll
        roll,             # Roll   <- col index 5
        0,                # DesPitch
        pitch,            # Pitch  <- col index 7
        0,                # DesYaw
        yaw,              # Yaw    <- col index 9
        0, 0,             # ErrRP, ErrYaw
        "", "", "", "",   # padding to 16 cols
    ])
    counter += 1

out = pd.DataFrame(rows)
out.to_csv("ardupilot_log.csv", index=False, header=True)
print("Saved ardupilot_log.csv:", out.shape)
print(out.head(4).to_string())
