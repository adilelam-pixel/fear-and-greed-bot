import os
import requests
import csv
from datetime import datetime
import pytz
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# Safe imports for data framing and charting
try:
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
except ImportError:
    pd = None
    plt = None
    mdates = None

url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
csv_filename = "fear_and_greed_history.csv"

COMPONENTS = {
    "market_momentum_sp500": "Market Momentum",
    "stock_price_strength": "Stock Price Strength",
    "stock_price_breadth": "Stock Price Breadth",
    "put_call_options": "Put and Call Options",
    "market_volatility_vix": "Market Volatility",
    "junk_bond_demand": "Junk Bond Demand",
    "safe_haven_demand": "Safe Haven Demand"
}

try:
    # --- 1. Fetch Live Sentiment Values ---
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    fgi_main = data.get("fear_and_greed", {})
    overall_score = round(fgi_main.get('score', 0), 2)
    overall_rating = fgi_main.get('rating', 'UNKNOWN').upper()
    
    # Get current time in France timezone (Europe/Paris)
    france_tz = pytz.timezone('Europe/Paris')
    current_time_france = datetime.now(france_tz)
    current_time = current_time_france.strftime("%Y-%m-%d %H:%M:%S")
    
    # Format French date as dd/MM/YYYY with time
    french_locale_date = current_time_france.strftime("%d/%m/%Y à %H:%M:%S %Z")
    
    row_data = {
        "Timestamp": current_time,
        "Overall Score": overall_score,
        "Overall Rating": overall_rating
    }
    
    for key, column_name in COMPONENTS.items():
        comp_data = data.get(key, {})
        score = comp_data.get("score")
        row_data[column_name] = round(score, 2) if score is not None else "N/A"

    # --- 2. Write to CSV Spreadsheet ---
    file_exists = os.path.isfile(csv_filename)
    fieldnames = ["Timestamp", "Overall Score", "Overall Rating"] + list(COMPONENTS.values())
    
    with open(csv_filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_data)

    # --- 3. Generate Clean "Light" Visual Chart ---
    if pd is not None and plt is not None and mdates is not None:
        df = pd.read_csv(csv_filename)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        df_recent = df.tail(30) # Focus on trailing 30 evaluations
        
        # Build canvas with flat white backdrop
        fig, ax = plt.subplots(figsize=(10, 4.5), facecolor='white')
        ax.set_facecolor('white')
        
        # Plot crisp, high-contrast overall index line
        ax.plot(df_recent['Timestamp'], df_recent['Overall Score'], color='#111111', linewidth=2.5, marker='o', markersize=4, label=f'Overall Index ({int(overall_score)})')
        
        # Plot subtle, lightweight component lines
        for col in COMPONENTS.values():
            if col in df_recent.columns and df_recent[col].dtype != object:
                ax.plot(df_recent['Timestamp'], df_recent[col], alpha=0.25, linewidth=1, linestyle='-')
                
        # Clean typography and subtle borders
        ax.set_title(f'Fear & Greed Index: {int(overall_score)} ({overall_rating})', fontsize=12, fontweight='bold', color='#222222', pad=12, loc='left')
        ax.set_ylabel('Score Scale', fontsize=9, color='#555555')
        ax.set_ylim(-5, 105)
        ax.grid(True, linestyle='--', linewidth=0.5, color='#e5e5e5')
        
        # Format x-axis with French date format dd/MM/YYYY HH:MM
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m/%Y %H:%M'))
        plt.xticks(rotation=45, ha='right')
        
        # Desaturate layout edges
        for edge in ['top', 'right']: ax.spines[edge].set_visible(False)
        for edge in ['left', 'bottom']: ax.spines[edge].set_color('#cccccc')
        ax.tick_params(colors='#555555', labelsize=9)
        
        plt.tight_layout()
        plt.savefig('fear_and_greed_chart.png', dpi=130, bbox_inches='tight', facecolor='white')
        plt.close()

    # --- 4. Send Email with Inline Content Object ---
    mail_user = os.environ.get("MAIL_USERNAME")
    mail_pass = os.environ.get("MAIL_PASSWORD")
    target_email = os.environ.get("TARGET_EMAIL")

    if mail_user and mail_pass and target_email:
        # 'related' structure enables linking image references inside HTML structures
        msg = MIMEMultipart('related')
        msg['Subject'] = f"Market Sentiment Alert: {int(overall_score)} ({overall_rating})"
        msg['From'] = f"Fear & Greed Cloud Bot <{mail_user}>"
        msg['To'] = target_email

        # Formatted email body referencing Content-ID (cid)
        html_body = f"""
        <html>
          <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #222222; margin: 15px; padding: 0;">
            <div style="max-width: 600px; margin: 0 auto; border: 1px solid #eaeaea; border-radius: 8px; padding: 20px; background-color: #ffffff;">
              <h3 style="margin-top: 0; font-size: 18px; color: #111111; font-weight: 600;">Daily Sentiment Scan</h3>
              <p style="font-size: 13px; color: #666666; margin-bottom: 20px;">Snapshot captured on {french_locale_date}</p>
              
              <div style="text-align: center; margin: 15px 0;">
                <img src="cid:embedded_trend_chart" alt="Historical Trend Graph" style="max-width: 100%; height: auto; display: block; margin: 0 auto;">
              </div>
              
              <hr style="border: 0; border-top: 1px solid #eeeeee; margin: 20px 0;">
              <p style="font-size: 11px; color: #999999; margin: 0; text-align: center;">Automated server transmission. No manual monitoring required.</p>
            </div>
          </body>
        </html>
        """
        msg.attach(MIMEText(html_body, 'html'))

        # Bind image binary stream into the specific container ID
        if os.path.exists('fear_and_greed_chart.png'):
            with open('fear_and_greed_chart.png', 'rb') as f:
                img_payload = MIMEImage(f.read())
            img_payload.add_header('Content-ID', '<embedded_trend_chart>')
            img_payload.add_header('Content-Disposition', 'inline', filename='fear_and_greed_chart.png')
            msg.attach(img_payload)

        # Authenticate connection and dispatch message
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(mail_user, mail_pass)
            server.sendmail(mail_user, target_email, msg.as_string())
        print("Email report dispatched successfully.")
            
except Exception as e:
    print(f"Error handling task sequence: {e}")
