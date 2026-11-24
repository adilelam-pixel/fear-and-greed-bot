import os
import sys
import math
import requests
import pandas as pd
import datetime
from zoneinfo import ZoneInfo  # Explicitly handle international timezones
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# --- Configuration & Global Variables ---
csv_filename = "fear_and_greed_history.csv"
# Mapping CNN's active JSON keys to your established human-readable CSV columns
COMPONENTS = {
    "market_momentum_sp500": "Market Momentum",
    "stock_price_strength": "Stock Price Strength",
    "stock_price_breadth": "Stock Price Breadth",
    "put_call_options": "Put and Call Options",
    "market_volatility_vix": "Market Volatility",
    "junk_bond_demand": "Junk Bond Demand",
    "safe_haven_demand": "Safe Haven Demand"
}
CSV_COLUMNS = ["Timestamp", "Overall Score", "Rating"] + list(COMPONENTS.values())

# --- 1. Fetch Live Sentiment Metrics from Active API Endpoint ---
print("[INFO] Initiating data collection sequence from live CNN endpoint...")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.cnn.com",
    "Referer": "https://www.cnn.com/"
}
url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

max_retries = 3
retry_delay = 10  # Seconds to wait before trying again due to network flux
data = None
for attempt in range(max_retries):
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()

        # Isolate active master index and enforce exactly 2 decimal places
        fng_now = data.get("fear_and_greed", {})
        overall_score = round(float(fng_now.get("score", 50.0)), 2)
        overall_rating = str(fng_now.get("rating", "NEUTRAL")).upper()
        print(f"[SUCCESS] Collected Core Index: {overall_score:.2f} ({overall_rating})")
        break  # Connection successful! Break out of loop.

    except Exception as e:
        print(f"[WARNING] Attempt {attempt + 1}/{max_retries} failed due to network error: {e}")
        if attempt < max_retries - 1:
            print(f"[INFO] Resting {retry_delay} seconds before re-attempting...")
            time.sleep(retry_delay)
        else:
            print("[FATAL ERROR] All network connection attempts completely exhausted.")
            sys.exit(1)

# --- 2. Update and Backfill Historical CSV Archive (French Timezone) ---
# Enforce the Europe/Paris timezone context regardless of runner server location.
french_tz = ZoneInfo("Europe/Paris")
now_paris = datetime.datetime.now(french_tz)
timestamp_str = now_paris.strftime("%Y-%m-%d %H:%M:%S")
today_key = now_paris.strftime("%Y-%m-%d")

# Build today's complete snapshot from the live API response.
new_row = {
    "Timestamp": timestamp_str,
    "Overall Score": overall_score,
    "Rating": overall_rating
}

for api_key, csv_column_name in COMPONENTS.items():
    comp_block = data.get(api_key, {}) or {}
    score_val = comp_block.get("score", 50.0)
    new_row[csv_column_name] = round(float(score_val), 2) if score_val is not None else 50.0

# Load existing CSV, preserving all existing observations.
if os.path.exists(csv_filename):
    df_history = pd.read_csv(csv_filename)
else:
    df_history = pd.DataFrame(columns=CSV_COLUMNS)

# Ensure the expected columns exist, without discarding any additional user columns.
for column in CSV_COLUMNS:
    if column not in df_history.columns:
        df_history[column] = pd.NA

extra_columns = [column for column in df_history.columns if column not in CSV_COLUMNS]
df_history = df_history[CSV_COLUMNS + extra_columns]

# Identify calendar dates already present in the CSV.
existing_dates = set()
if not df_history.empty:
    existing_timestamps = pd.to_datetime(df_history["Timestamp"], errors="coerce")
    existing_dates = set(
        existing_timestamps.dt.strftime("%Y-%m-%d").dropna().tolist()
    )

# CNN provides a daily history for the headline index. Use it to fill missing dates.
# Historical subcomponent values in CNN's data arrays are not the same as the
# normalized 0-100 component scores stored in this CSV, so those cells are left blank.
historical_block = data.get("fear_and_greed_historical", {}) or {}
historical_points = historical_block.get("data", []) or []
backfill_rows = []

if not isinstance(historical_points, list) or not historical_points:
    print("[WARNING] CNN historical series is missing or empty; no backfill was performed.")
else:
    for point in historical_points:
        try:
            timestamp_ms = float(point["x"])
            historical_score = float(point["y"])
            if not math.isfinite(timestamp_ms) or not math.isfinite(historical_score):
                continue

            # CNN timestamps are Unix milliseconds. The date key is taken in UTC,
            # matching the calendar date used by CNN for its daily historical point.
            date_utc = datetime.datetime.fromtimestamp(
                timestamp_ms / 1000,
                tz=datetime.timezone.utc
            )
            date_key = date_utc.strftime("%Y-%m-%d")
        except (KeyError, TypeError, ValueError, OverflowError, OSError) as error:
            print(f"[WARNING] Skipping malformed CNN historical point: {error}")
            continue

        # Do not add dates already represented in the CSV or today's live snapshot.
        if date_key in existing_dates or date_key == today_key:
            continue

        # Keep CNN's real timestamp converted to Paris time. Historical component
        # scores remain empty rather than inventing values or copying raw indicators.
        historical_timestamp = date_utc.astimezone(french_tz).strftime("%Y-%m-%d %H:%M:%S")
        historical_rating = str(point.get("rating") or "").upper()

        historical_row = {column: pd.NA for column in CSV_COLUMNS}
        historical_row.update({
            "Timestamp": historical_timestamp,
            "Overall Score": round(historical_score, 2),
            "Rating": historical_rating
        })

        backfill_rows.append(historical_row)
        existing_dates.add(date_key)  # Prevent duplicate insertions from the API list.

if backfill_rows:
    df_backfill = pd.DataFrame(backfill_rows, columns=CSV_COLUMNS)
    df_history = pd.concat([df_history, df_backfill], ignore_index=True)
    print(f"[INFO] Backfilled {len(backfill_rows)} missing historical dates from CNN.")
else:
    print("[INFO] No missing historical dates to backfill.")

# Append the current live snapshot after backfilling.
df_history = pd.concat([df_history, pd.DataFrame([new_row])], ignore_index=True)

# Sort chronologically. Existing intraday observations and duplicates are retained.
parsed_timestamps = pd.to_datetime(df_history["Timestamp"], errors="coerce")
df_history = (
    df_history.assign(_sort_timestamp=parsed_timestamps)
    .sort_values("_sort_timestamp", kind="stable", na_position="last")
    .drop(columns="_sort_timestamp")
)

# Normalize valid timestamps while leaving any unparseable original value untouched.
parsed_timestamps = pd.to_datetime(df_history["Timestamp"], errors="coerce")
formatted_timestamps = parsed_timestamps.dt.strftime("%Y-%m-%d %H:%M:%S")
df_history["Timestamp"] = formatted_timestamps.where(
    parsed_timestamps.notna(), df_history["Timestamp"]
)

df_history.to_csv(csv_filename, index=False)
print(
    f"[INFO] History database synced successfully ({timestamp_str} Paris Time). "
    f"Total rows: {len(df_history)}"
)

# --- 3. Generate Full-History Chart ---
print("[INFO] Generating full-history Fear & Greed chart...")

df = pd.read_csv(csv_filename)
df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
df = df.dropna(subset=["Timestamp"]).sort_values("Timestamp")

if df.empty:
    print("[FATAL ERROR] CSV contains no valid timestamps; cannot generate chart.")
    sys.exit(1)

# Keep every available observation: do not truncate to the last 30 rows.
df_all = df.copy()

# Two dedicated panels: headline index on top, seven components below.
fig, (ax_overall, ax_components) = plt.subplots(
    2,
    1,
    figsize=(15, 10),
    sharex=True,
    gridspec_kw={"height_ratios": [1, 1.35]},
    facecolor="white"
)
fig.patch.set_facecolor("white")
ax_overall.set_facecolor("white")
ax_components.set_facecolor("white")

# Consistent component palette.
COMPONENT_COLORS = {
    "Market Momentum": "#1f77b4",
    "Stock Price Strength": "#ff7f0e",
    "Stock Price Breadth": "#2ca02c",
    "Put and Call Options": "#d62728",
    "Market Volatility": "#9467bd",
    "Junk Bond Demand": "#8c564b",
    "Safe Haven Demand": "#e377c2"
}

# Panel 1: complete historical headline index.
overall_values = pd.to_numeric(df_all["Overall Score"], errors="coerce")
ax_overall.plot(
    df_all["Timestamp"],
    overall_values,
    color="#111111",
    linewidth=1.8,
    marker="o",
    markersize=2.5,
    label="Overall Index"
)
ax_overall.set_title(
    f"Overall Fear & Greed Index — {len(df_all)} observations",
    fontsize=12,
    fontweight="bold",
    color="#222222",
    loc="left",
    pad=10
)
ax_overall.set_ylabel("Overall score", fontsize=9, color="#555555")
ax_overall.set_ylim(-5, 105)
ax_overall.grid(True, linestyle="--", linewidth=0.5, color="#e5e5e5")
ax_overall.legend(loc="upper left", fontsize=8, framealpha=0.95)

# Panel 2: complete available history for each component.
# CNN backfilled rows contain no normalized historical component scores;
# pandas NaN values intentionally create visible gaps rather than fabricated lines.
for col in COMPONENTS.values():
    if col not in df_all.columns:
        continue

    component_values = pd.to_numeric(df_all[col], errors="coerce")
    ax_components.plot(
        df_all["Timestamp"],
        component_values,
        alpha=0.85,
        linewidth=1.15,
        linestyle="-",
        color=COMPONENT_COLORS.get(col, "#7f7f7f"),
        label=col
    )

ax_components.set_title(
    "Fear & Greed — Seven Components (all available observations)",
    fontsize=12,
    fontweight="bold",
    color="#222222",
    loc="left",
    pad=10
)
ax_components.set_ylabel("Component score", fontsize=9, color="#555555")
ax_components.set_ylim(-5, 105)
ax_components.set_xlabel("Date", fontsize=9, color="#555555")
ax_components.grid(True, linestyle="--", linewidth=0.5, color="#e5e5e5")
ax_components.legend(
    loc="upper left",
    bbox_to_anchor=(1.01, 1),
    fontsize=8,
    framealpha=0.95,
    edgecolor="#cccccc",
    facecolor="white"
)

# Date axis spans the first through the last valid observation in the CSV.
ax_components.xaxis.set_major_locator(
    mdates.AutoDateLocator(minticks=6, maxticks=12)
)
ax_components.xaxis.set_major_formatter(
    mdates.DateFormatter("%d/%m/%Y")
)
plt.setp(ax_components.get_xticklabels(), rotation=30, ha="right", fontsize=8)

for axis in (ax_overall, ax_components):
    for edge in ["top", "right"]:
        axis.spines[edge].set_visible(False)
    for edge in ["left", "bottom"]:
        axis.spines[edge].set_color("#cccccc")
    axis.tick_params(colors="#555555", labelsize=8)

fig.suptitle(
    f"Fear & Greed Index: {overall_score:.2f} ({overall_rating})",
    fontsize=15,
    fontweight="bold",
    color="#222222",
    x=0.08,
    ha="left",
    y=0.99
)
fig.tight_layout(rect=[0, 0, 0.83, 0.96])

chart_filename = "fear_and_greed_chart.png"
plt.savefig(chart_filename, dpi=150, bbox_inches="tight", facecolor="white")
plt.close(fig)

print(
    f"[INFO] Full-history chart saved successfully: {len(df_all)} observations, "
    f"{df_all['Timestamp'].min()} to {df_all['Timestamp'].max()}."
)

# --- 4. Package and Dispatch Email Notifications ---
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
TARGET_EMAIL = os.environ.get("TARGET_EMAIL")

if not all([MAIL_USERNAME, MAIL_PASSWORD, TARGET_EMAIL]):
    print("[WARNING] Email credential environment keys missing. Exiting gracefully without dispatch.")
    sys.exit(0)

print(f"[INFO] Formatting email transmission context to {TARGET_EMAIL}...")
msg = MIMEMultipart("related")
msg["Subject"] = f"Daily Market Sentiment Report: {overall_score:.2f} ({overall_rating})"
msg["From"] = MAIL_USERNAME
msg["To"] = TARGET_EMAIL

html_content = f"""
<html>
  <body style="font-family: Arial, sans-serif; color: #333333; line-height: 1.6;">
    <h2 style="color: #222222; margin-bottom: 5px;">Fear &amp; Greed Market Index Update</h2>
    <p style="font-size: 11px; color: #888888; margin-top: 0;">Evaluation Timestamp: {timestamp_str} (Paris Time)</p>
    <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;" />
    <p style="font-size: 16px;">
      Current Market Sentiment Value:
      <strong style="font-size: 18px; color: #111111;">{overall_score:.2f}</strong>
      (<span style="font-weight: bold; color: #555555;">{overall_rating}</span>)
    </p>

    <div style="margin: 25px 0;">
      <img src="cid:sentiment_chart_stream" alt="Fear and Greed Component Analysis Plot" style="max-width: 100%; height: auto; border: 1px solid #e0e0e0; border-radius: 4px;" />
    </div>
    <p style="font-size: 12px; color: #aaaaaa; margin-top: 30px;">
      This email was generated automatically via centralized repository pipelines. Data source courtesy of CNN Business Market Metrics.
    </p>
  </body>
</html>
"""
msg.attach(MIMEText(html_content, "html"))

# Read and attach chart image file inline
try:
    with open(chart_filename, "rb") as img_file:
        img_data = img_file.read()

    email_image = MIMEImage(img_data)
    email_image.add_header("Content-ID", "<sentiment_chart_stream>")
    email_image.add_header("Content-Disposition", "inline", filename=chart_filename)
    msg.attach(email_image)

    # Establish server connection via Gmail SMTP relays
    print("[INFO] Connecting to outbound mail servers...")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_USERNAME, TARGET_EMAIL, msg.as_string())

    print("[SUCCESS] Automated sentiment visual delivery run complete.")
except Exception as mail_error:
    print(f"[ERROR] Email transmission processing aborted: {mail_error}")
