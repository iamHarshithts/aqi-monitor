from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
import time

app = Flask(__name__)
CORS(app)

# --- REPLACE WITH YOUR API KEY ---
API_KEY = "9c9815bb312b7d2d7b1dda93051932a5"

# --- 1. INDIAN AQI CALCULATION LOGIC ---
# Breakpoints for CPCB (Indian) Standard (0-500 scale)
BREAKPOINTS = {
    "pm2_5": [[0, 30, 0, 50], [30, 60, 51, 100], [60, 90, 101, 200], [90, 120, 201, 300], [120, 250, 301, 400], [250, 400, 401, 500]],
    "pm10":  [[0, 50, 0, 50], [50, 100, 51, 100], [100, 250, 101, 200], [250, 350, 201, 300], [350, 430, 301, 400], [430, 500, 401, 500]],
    "no2":   [[0, 40, 0, 50], [40, 80, 51, 100], [80, 180, 101, 200], [180, 280, 201, 300], [280, 400, 301, 400], [400, 500, 401, 500]],
    "so2":   [[0, 40, 0, 50], [40, 80, 51, 100], [80, 380, 101, 200], [380, 800, 201, 300], [800, 1600, 301, 400], [1600, 2000, 401, 500]],
    "co":    [[0, 1.0, 0, 50], [1.0, 2.0, 51, 100], [2.0, 10, 101, 200], [10, 17, 201, 300], [17, 34, 301, 400], [34, 50, 401, 500]]
}

def calculate_sub_index(conc, pollutant):
    bp_list = BREAKPOINTS.get(pollutant)
    if not bp_list: return 0
    for (clo, chi, ilo, ihi) in bp_list:
        if clo <= conc <= chi:
            return ilo + ((ihi - ilo) / (chi - clo)) * (conc - clo)
    return 500 # Cap at 500 if extremely high
def get_indian_aqi(components):
    # Prepare concentrations (CO from ug/m3 -> mg/m3)
    co_mg = components.get('co', 0) / 1000.0
    
    # Calculate sub-indices for ALL pollutants
    idx_pm25 = calculate_sub_index(components.get('pm2_5', 0), "pm2_5")
    idx_pm10 = calculate_sub_index(components.get('pm10', 0), "pm10")
    idx_no2  = calculate_sub_index(components.get('no2', 0), "no2")
    idx_so2  = calculate_sub_index(components.get('so2', 0), "so2")
    idx_co   = calculate_sub_index(co_mg, "co")
    
    # --- DEBUGGING PRINT (Check your Terminal!) ---
    print(f"--- AQI BREAKDOWN ---")
    print(f"PM2.5: {components.get('pm2_5')} -> Index: {idx_pm25}")
    print(f"PM10 : {components.get('pm10')}  -> Index: {idx_pm10}")
    print(f"NO2  : {components.get('no2')}   -> Index: {idx_no2}")
    print(f"SO2  : {components.get('so2')}   -> Index: {idx_so2}")
    print(f"CO   : {co_mg:.2f} mg/m3      -> Index: {idx_co}")
    print(f"FINAL MAX AQI: {int(max(idx_pm25, idx_pm10, idx_no2, idx_so2, idx_co))}")
    print("---------------------")

    # Final AQI is the Max of sub-indices
    return int(max(idx_pm25, idx_pm10, idx_no2, idx_so2, idx_co))
def get_aqi_label(aqi):
    if aqi <= 50: return "Good", "#00B050"
    if aqi <= 100: return "Satisfactory", "#92D050"
    if aqi <= 200: return "Moderate", "#FFFF00"
    if aqi <= 300: return "Poor", "#FF9900"
    if aqi <= 400: return "Very Poor", "#FF0000"
    return "Severe", "#C00000"

# --- 2. API ROUTES ---
@app.route('/')
def home():
    return render_template('index.html')
@app.route('/get-pollution', methods=['GET'])
def get_pollution():
    lat = request.args.get('lat')
    lon = request.args.get('lon')

    if not lat or not lon:
        return jsonify({"error": "Missing lat/lon"}), 400

    try:
        # A. Get CURRENT Data
        url_now = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={API_KEY}"
        resp_now = requests.get(url_now).json()
        
        # B. Get FORECAST Data
        url_fore = f"http://api.openweathermap.org/data/2.5/air_pollution/forecast?lat={lat}&lon={lon}&appid={API_KEY}"
        resp_fore = requests.get(url_fore).json()

        # 1. Process Current
        current_comps = resp_now['list'][0]['components']
        current_aqi = get_indian_aqi(current_comps)
        c_label, c_color = get_aqi_label(current_aqi)

        # 2. Process Forecast (Next 3 Days)
        # API returns hourly blocks. 
        # Index 24 = +24 hours (Tomorrow)
        # Index 48 = +48 hours (Day After)
        # Index 72 = +72 hours (3rd Day)
        forecast_result = []
        indices_to_check = [24, 48, 72] 

        for i in indices_to_check:
            if i < len(resp_fore['list']):
                item = resp_fore['list'][i]
                
                # --- CRITICAL: Calculate Indian AQI for this specific forecast day ---
                f_comps = item['components']
                f_aqi = get_indian_aqi(f_comps) 
                f_label, f_color = get_aqi_label(f_aqi)

                forecast_result.append({
                    "dt": item['dt'],
                    "aqi": f_aqi,            # This is the value you wanted
                    "aqi_label": f_label,    # Text (Good/Poor)
                    "aqi_color": f_color,    # Color for UI
                    "main_pollutant": "PM2.5", # Simplified assumption
                    "components": f_comps
                })

        # 3. Return Final JSON
        return jsonify({
            "current": {
                "aqi": current_aqi,
                "label": c_label,
                "color": c_color,
                "components": current_comps
            },
            "forecast": forecast_result
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "Failed to fetch data"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)