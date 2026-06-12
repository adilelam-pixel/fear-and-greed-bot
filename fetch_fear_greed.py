import os
import sys
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

# --- 1. Fetch Live Sentiment Metrics from Active API Endpoint ---
print("[INFO] Initiating data collection sequence from live CNN endpoint...")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"

max_retries = 3
retry_delay = 10  # Seconds to wait before trying again due to network flux
data = None

for attempt in range(max_retries):
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        # Isolate active master indices
        fng_now = data.get("fear_and_greed", {})
        overall_score = fng_now.get("score", 50)
        overall_rating = str(fng_now.get("rating", "NEUTRAL")).upper()
        
        print(f"[SUCCESS] Collected Core Index: {int(overall_score)} ({overall_rating})")
        break  # Connection successful! Break out of loop.
        
    except Exception as e:
        print(f"[WARNING] Attempt {attempt + 1}/{max_retries} failed due to network error: {e}")
        if attempt < max_retries - 1:
            print(f"[INFO] Resting {retry_delay} seconds before re-attempting...")
            time.sleep(retry_delay)
        else:
            print("[FATAL ERROR] All network connection attempts completely exhausted.")
            sys.exit(1)

# --- 2. Update and Append Historical CSV Archive (French Timezone) ---
# Enforce the Europe/Paris timezone context regardless of runner server location
french_tz = ZoneInfo("Europe/Paris")
timestamp_str = datetime.datetime.now(french_tz).strftime("%Y-%m-%d %H:%M:%S")

new_row = {
    "Timestamp": timestamp_str,
    "Overall Score": overall_score,
    "Rating": overall_rating
}

# Parse sub-components out of the active JSON contract
for api_key, csv_column_name in COMPONENTS.items():
    comp_block = data.get(api_key, {})
    score_val = comp_block.get("score", 50)
    new_row[csv_column_name] = score_val if score_val is not None else 50

# Load existing log tracking database or create a new one if missing
if os.path.exists(csv_filename):
    df_history = pd.read_csv(csv_filename)
else:
    columns = ["Timestamp", "Overall Score", "Rating"] + list(COMPONENTS.values())
    df_history = pd.DataFrame(columns=columns)

df_history = pd.concat([df_history, pd.DataFrame([new_row])], ignore_index=True)
df_history.to_csv(csv_filename, index=False)
print(f"[INFO] History database synced successfully ({timestamp_str} French Time). Total rows: {len(df_history)}")

# --- 3. Generate Clean High-Contrast Visual Chart ---
print("[INFO] Generating optimized high-contrast chart...")
df = pd.read_csv(csv_filename)
df['Timestamp'] = pd.to_datetime(df['Timestamp'])
df_recent = df.tail(30)  # Focus on trailing 30 evaluations to preserve detail

# Build canvas with flat white backdrop
fig, ax = plt.subplots(figsize=(13, 6), facecolor='white')
ax.set_facecolor('white')

# Explicit color mapping palette for zero-blur distinct identification
COMPONENT_COLORS = {
    "Market Momentum": "#1f77b4",       # Electric Blue
    "Stock Price Strength": "#ff7f0e",   # Safety Orange
    "Stock Price Breadth": "#2ca02c",    # Forest Green
    "Put and Call Options": "#d62728",   # Crimson Red
    "Market Volatility": "#9467bd",      # Deep Purple
    "Junk Bond Demand": "#8c564b",       # Cocoa Brown
    "Safe Haven Demand": "#e377c2"       # Vibrant Pink
}

# Plot sub-component tracks
for col in COMPONENTS.values():
    if col in df_recent.columns and df_recent[col].dtype != object:
        label = f'**{col}**' if col in ['Market Momentum', 'Market Volatility'] else col
        color = COMPONENT_COLORS.get(col, "#7f7f7f")
        
        ax.plot(
            df_recent['Timestamp'], 
            df_recent[col], 
            alpha=0.5,          # Stable opacity to make fine lines distinct
            linewidth=1.2,      
            linestyle='-', 
            color=color, 
            label=label
        )

# Plot overall master index line (Ultra-bold high-contrast black line)
ax.plot(
    df_recent['Timestamp'], 
    df_recent['Overall Score'], 
    color='#111111', 
    linewidth=3.5, 
    marker='o', 
    markersize=5, 
    label='**Overall Index**'
)
        
# Layout decorations
ax.set_title(f'Fear & Greed Index: {int(overall_score)} ({overall_rating})', fontsize=13, fontweight='bold', color='#222222', pad=15, loc='left')
ax.set_ylabel('Score Scale', fontsize=9, color='#555555')
ax.set_ylim(-5, 105)
ax.grid(True, linestyle='--', linewidth=0.5, color='#e5e5e5')

# AutoDateLocator intelligently prevents label crowding across dynamic timelines
ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y\n%H:%M'))
plt.xticks(rotation=30, ha='right', fontsize=8)

# Legend positioning outside active chart window
legend = ax.legend(loc='upper left', fontsize=8, framealpha=0.95, edgecolor='#cccccc', facecolor='white', bbox_to_anchor=(1.02, 1))

# Unpack markdown bold triggers within legend components
for text in legend.get_texts():
    label_text = text.get_text()
    if '**' in label_text:
        label_text = label_text.replace('**', '')
        text.set_text(label_text)
        text.set_weight('bold')

# Desaturate axis borders
for edge in ['top', 'right']: ax.spines[edge].set_visible(False)
for edge in ['left', 'bottom']: ax.spines[edge].set_color('#cccccc')
ax.tick_params(colors='#555555', labelsize=9)

plt.tight_layout()
chart_filename = 'fear_and_greed_chart.png'
plt.savefig(chart_filename, dpi=130, bbox_inches='tight', facecolor='white')
plt.close()
print("[INFO] Optimized chart saved successfully.")

# --- 4. Package and Dispatch Email Notifications ---
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
TARGET_EMAIL = os.environ.get("TARGET_EMAIL")

if not all([MAIL_USERNAME, MAIL_PASSWORD, TARGET_EMAIL]):
    print("[WARNING] Email credential environment keys missing. Exiting gracefully without dispatch.")
    sys.exit(0)

print(f"[INFO] Formatting email transmission context to {TARGET_EMAIL}...")
msg = MIMEMultipart('related')
msg['Subject'] = f"Daily Market Sentiment Report: {int(overall_score)} ({overall_rating})"
msg['From'] = MAIL_USERNAME
msg['To'] = TARGET_EMAIL

# HTML body structure with embedded asset reference tags
html_content = f"""
<html>
  <body style="font-family: Arial, sans-serif; color: #333333; line-height: 1.6;">
    <h2 style="color: #222222; margin-bottom: 5px;">Fear & Greed Market Index Update</h2>
    <p style="font-size: 11px; color: #888888; margin-top: 0;">Evaluation Timestamp: {timestamp_str} (Paris Time)</p>
    <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;" />
    
    <p style="font-size: 16px;">
      Current Market Sentiment Value: 
      <strong style="font-size: 18px; color: #111111;">{int(overall_score)}</strong> 
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

msg.attach(MIMEText(html_content, 'html'))

# Read and attach chart image file inline
try:
    with open(chart_filename, 'rb') as img_file:
        img_data = img_file.read()
    
    email_image = MIMEImage(img_data)
    email_image.add_header('Content-ID', '<sentiment_chart_stream>')
    email_image.add_header('Content-Disposition', 'inline', filename=chart_filename)
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
