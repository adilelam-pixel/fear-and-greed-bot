import requests
import csv
import os
from datetime import datetime

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

    file_exists = os.path.isfile(csv_filename)
    fieldnames = ["Timestamp", "Overall Score", "Overall Rating"] + list(COMPONENTS.values())
    
    with open(csv_filename, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row_data)
        
    print(f"Successfully saved data for {current_time}")
    
except Exception as e:
    print(f"Error: {e}")
