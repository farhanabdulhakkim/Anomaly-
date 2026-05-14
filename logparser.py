"""
ardupilot_log_parser.py
=======================
Extracts a clean dataset from an ArduPilot CSV-exported flight log.

Output fields
-------------
- Timestamp      : Wall-clock datetime (already embedded in the log)
- Latitude       : Decimal degrees (from GPS, POS as fallback)
- Longitude      : Decimal degrees (from GPS, POS as fallback)
- Altitude_m     : Metres above sea level
- Roll_deg       : Roll angle  (degrees, + = right-wing down)
- Pitch_deg      : Pitch angle (degrees, + = nose up)
- Yaw_deg        : Yaw / heading (degrees, 0 = North)
- Speed_ms       : Horizontal ground-speed (m/s, from GPS)

Log structure recap
-------------------
The ArduPilot CSV has one row per log message.
Column layout (positional, independent of header names):
  index 0  -> internal line counter
  index 1  -> wall-clock timestamp string  e.g. '2026-04-02 17:00:28.000'
  index 2  -> message type  e.g. GPS, ATT, POS
  index 3+ -> message payload fields (positional per message type)

Key message types used
  GPS  fields  [3]=TimeUS [4]=Status [10]=Lat [11]=Lng [12]=Alt [13]=Spd_ms
  ATT  fields  [3]=TimeUS [5]=Roll   [7]=Pitch [9]=Yaw
  POS  fields  [3]=TimeUS [4]=Lat    [5]=Lng   [6]=Alt   (fallback for GPS)
"""

import os
import sys
import logging
import pandas as pd

# -- Configuration ------------------------------------------------------------

INPUT_FILE  = "ardupilot_log.csv"
OUTPUT_FILE = "output/flight_clean.csv"

# Positional column indices inside the raw dataframe (0-based)
COL_TIMESTAMP = 1   # wall-clock datetime string
COL_MSGTYPE   = 2   # message type label

# GPS message field positions
GPS_COL_LAT   = 10
GPS_COL_LNG   = 11
GPS_COL_ALT   = 12
GPS_COL_SPD   = 13  # ground speed m/s

# ATT message field positions
ATT_COL_ROLL  = 5   # Roll  (degrees)
ATT_COL_PITCH = 7   # Pitch (degrees)
ATT_COL_YAW   = 9   # Yaw   (degrees)

# POS message field positions (fallback lat/lng)
POS_COL_LAT   = 4
POS_COL_LNG   = 5
POS_COL_ALT   = 6

# -- Logging setup -------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


# -- Helper functions ----------------------------------------------------------

def load_raw_log(path: str) -> pd.DataFrame:
    log.info("Loading log file: %s", path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Log file not found: {path}")

    df = pd.read_csv(
        path,
        header=0,
        on_bad_lines="skip",
        engine="python",
        dtype=str,
    )
    log.info("Raw log loaded: %d rows x %d columns", *df.shape)
    return df


def parse_timestamp(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def extract_message(df: pd.DataFrame, msg_type: str) -> pd.DataFrame:
    mask   = df.iloc[:, COL_MSGTYPE] == msg_type
    subset = df.loc[mask].copy()
    if subset.empty:
        log.warning("No rows found for message type '%s'.", msg_type)
        return subset
    subset["_ts"] = parse_timestamp(subset.iloc[:, COL_TIMESTAMP])
    log.info("  %-6s  %d rows", msg_type, len(subset))
    return subset


def safe_float(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def build_gps_df(raw: pd.DataFrame) -> pd.DataFrame:
    gps = extract_message(raw, "GPS")

    if not gps.empty:
        out = pd.DataFrame({
            "_ts"        : gps["_ts"],
            "Latitude"   : safe_float(gps.iloc[:, GPS_COL_LAT]),
            "Longitude"  : safe_float(gps.iloc[:, GPS_COL_LNG]),
            "Altitude_m" : safe_float(gps.iloc[:, GPS_COL_ALT]),
            "Speed_ms"   : safe_float(gps.iloc[:, GPS_COL_SPD]),
        })
        out.loc[out["Latitude"].abs()  > 90,  "Latitude"]  = float("nan")
        out.loc[out["Longitude"].abs() > 180, "Longitude"] = float("nan")
        log.info("GPS source: GPS messages (%d rows)", len(out))
        return out.dropna(subset=["_ts"]).reset_index(drop=True)

    log.warning("GPS messages absent; falling back to POS messages.")
    pos = extract_message(raw, "POS")
    if pos.empty:
        log.error("Neither GPS nor POS messages found. Lat/Lng will be empty.")
        return pd.DataFrame(columns=["_ts", "Latitude", "Longitude", "Altitude_m", "Speed_ms"])

    out = pd.DataFrame({
        "_ts"        : pos["_ts"],
        "Latitude"   : safe_float(pos.iloc[:, POS_COL_LAT]),
        "Longitude"  : safe_float(pos.iloc[:, POS_COL_LNG]),
        "Altitude_m" : safe_float(pos.iloc[:, POS_COL_ALT]),
        "Speed_ms"   : float("nan"),
    })
    log.info("GPS source: POS fallback (%d rows)", len(out))
    return out.dropna(subset=["_ts"]).reset_index(drop=True)


def build_att_df(raw: pd.DataFrame) -> pd.DataFrame:
    att = extract_message(raw, "ATT")
    if att.empty:
        return pd.DataFrame(columns=["_ts", "Roll_deg", "Pitch_deg", "Yaw_deg"])

    out = pd.DataFrame({
        "_ts"      : att["_ts"],
        "Roll_deg" : safe_float(att.iloc[:, ATT_COL_ROLL]),
        "Pitch_deg": safe_float(att.iloc[:, ATT_COL_PITCH]),
        "Yaw_deg"  : safe_float(att.iloc[:, ATT_COL_YAW]),
    })
    return out.dropna(subset=["_ts"]).reset_index(drop=True)


def merge_by_nearest_time(
    left: pd.DataFrame,
    right: pd.DataFrame,
    tolerance_ms: int = 500,
) -> pd.DataFrame:
    if left.empty or right.empty:
        combined = left.merge(right, on="_ts", how="outer") if not left.empty else right
        return combined

    merged = pd.merge_asof(
        left.sort_values("_ts"),
        right.sort_values("_ts"),
        on="_ts",
        direction="nearest",
        tolerance=pd.Timedelta(milliseconds=tolerance_ms),
    )
    return merged


def build_clean_dataset(input_path: str) -> pd.DataFrame:
    raw    = load_raw_log(input_path)

    log.info("Extracting message types...")
    gps_df = build_gps_df(raw)
    att_df = build_att_df(raw)

    log.info("Merging GPS and ATT records by nearest timestamp...")
    merged = merge_by_nearest_time(gps_df, att_df, tolerance_ms=500)

    merged.rename(columns={"_ts": "Timestamp"}, inplace=True)

    final_cols = ["Timestamp", "Latitude", "Longitude", "Altitude_m",
                  "Roll_deg", "Pitch_deg", "Yaw_deg", "Speed_ms"]
    present = [c for c in final_cols if c in merged.columns]
    clean   = merged[present].copy()

    key_cols = [c for c in ["Latitude", "Longitude", "Roll_deg"] if c in clean.columns]
    clean.dropna(subset=key_cols, how="all", inplace=True)
    clean.reset_index(drop=True, inplace=True)

    log.info("Clean dataset: %d rows x %d columns", *clean.shape)
    return clean


# -- Entry point ---------------------------------------------------------------

def main():
    clean_df = build_clean_dataset(INPUT_FILE)

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    clean_df.to_csv(OUTPUT_FILE, index=False)
    log.info("Saved clean dataset -> %s", OUTPUT_FILE)

    print("\n-- Sample output (first 5 rows) --")
    print(clean_df.head().to_string(index=False))
    print("\n-- Column summary --")
    print(clean_df.describe(include="all").to_string())

    return clean_df


if __name__ == "__main__":
    main()
