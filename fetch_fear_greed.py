import requests
import csv
import os
from datetime import datetime

# Safe imports for the GitHub runner environment
try:
    import pandas as pd
    import matplotlib.pyplot as plt
except ImportError:
    pd = None
    plt = None

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
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
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
        
    print(f"Successfully saved data for {current_time}")

    # --- 3. Generate Historical Visual Chart ---
    if pd is not None and plt is not None:
        df = pd.read_csv(csv_filename)
        df['Timestamp'] = pd.to_datetime(df['Timestamp'])
        
        # Focus on the most recent 30 entries so the chart stays readable
        df_recent = df.tail(30)
        
        plt.figure(figsize=(12, 6))
        
        # Plot the primary bold index trendline
        plt.plot(df_recent['Timestamp'], df_recent['Overall Score'], label=f'Overall Index ({int(overall_score)})', color='black', linewidth=3.5, marker='o')
        
        # Plot the 7 background sub-components with thinner, dashed lines
        for col in COMPONENTS.values():
            if col in df_recent.columns and df_recent[col].dtype != object:
                plt.plot(df_recent['Timestamp'], df_recent[col], label=col, alpha=0.35, linestyle='--')
        
        plt.title(f'Fear & Greed Historical Trend\nCurrent Status: {int(overall_score)} ({overall_rating})', fontsize=13, fontweight='bold', pad=15)
        plt.ylabel('Score (0 - 100)')
        plt.ylim(-5, 105)
        plt.grid(True, linestyle=':', alpha=0.5)
        plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0)
        
        # Color accent bands across the background chart canvas
        plt.axhspan(0, 25, color='red', alpha=0.03)
        plt.axhspan(25, 45, color='orange', alpha=0.03)
        plt.axhspan(45, 55, color='gray', alpha=0.03)
        plt.axhspan(55, 75, color='lightgreen', alpha=0.03)
        plt.axhspan(75, 100, color='green', alpha=0.03)
        
        # Export visual image output
        plt.savefig('fear_and_greed_chart.png', dpi=150, bbox_inches='tight')
        plt.close()
        print("Chart successfully rendered as fear_and_greed_chart.png")
            
except Exception as e:
    print(f"Execution Error: {e}")
