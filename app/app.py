import streamlit as st
import requests
import joblib
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

# =========================
# Page Config
# =========================
st.set_page_config(
    page_title="Solar Irradiance Predictor",
    layout="centered"
)

st.title("Solar Irradiance Predictor")
with st.expander("About this app"):
    st.markdown("""
### Solar Irradiance Predictor

This app uses a trained **XGBoost regression model** to predict solar irradiance (W/m^2).

**Features used:**
- Temperature  
- Hour of day  
- Day of year  
- Cloud cover  

**Modes:**
- **Current** → Live weather data  
- **Historical** → Past weather + daily solar curve  
- **Manual** → Custom inputs for simulation  

**Note:**
- Model trained on historical NASA + weather data  
- Most accurate during daylight hours  
- Slight deviations near sunrise/sunset are expected  
""")
st.markdown("Predict solar irradiance using ML + weather data")

# =========================
# Load Model
# =========================
model = joblib.load("model/xgboost_irradiance_v1.joblib")

# =========================
# Core Prediction
# =========================
def predict_core(temp, hour, dayofyear, cloud):
    X = [[temp, hour, dayofyear, cloud]]
    irr = model.predict(X)[0]
    return max(0, irr)

# =========================
# Fetch Current Weather
# =========================
def fetch_current_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    
    params = {
        "latitude": 28.7041,
        "longitude": 77.1025,
        "current_weather": True,
        "hourly": "cloudcover",
        "timezone": "Asia/Kolkata"
    }
    
    data = requests.get(url, params=params).json()
    
    temp = data["current_weather"]["temperature"]
    current_time = data["current_weather"]["time"]
    
    times = data["hourly"]["time"]
    clouds = data["hourly"]["cloudcover"]
    
    cloud = None
    for t, c in zip(times, clouds):
        if t == current_time:
            cloud = c
            break
    
    if cloud is None:
        cloud = clouds[0]
    
    return float(temp), float(cloud)

# =========================
# Fetch Past Weather
# =========================
def fetch_past_weather(date_str, hour):
    url = "https://archive-api.open-meteo.com/v1/archive"
    
    params = {
        "latitude": 28.7041,
        "longitude": 77.1025,
        "start_date": date_str,
        "end_date": date_str,
        "hourly": ["temperature_2m", "cloudcover"],
        "timezone": "Asia/Kolkata"
    }
    
    data = requests.get(url, params=params).json()
    
    times = data["hourly"]["time"]
    temps = data["hourly"]["temperature_2m"]
    clouds = data["hourly"]["cloudcover"]
    
    target_time = f"{date_str}T{hour:02d}:00"
    
    for t, temp, cloud in zip(times, temps, clouds):
        if t == target_time:
            return float(temp), float(cloud)
    
    raise ValueError("Time not found")

# =========================
# Generate Daily Curve
# =========================
def generate_day_curve(date_str):
    hours = list(range(6, 19))
    preds = []
    
    for h in hours:
        try:
            temp, cloud = fetch_past_weather(date_str, h)
            dt = datetime.fromisoformat(f"{date_str}T{h:02d}:00")
            dayofyear = dt.timetuple().tm_yday
            
            pred = predict_core(temp, h, dayofyear, cloud)
            preds.append(pred)
        except:
            preds.append(0)
    
    df = pd.DataFrame({
        "hour": hours,
        "irradiance": preds
    })
    
    return df

# =========================
# Mode Selection
# =========================
mode = st.selectbox(
    "Select Mode",
    ["Current", "Historical", "Manual"]
)

# =========================
# MODE 1: CURRENT
# =========================
if mode == "Current":
    if st.button("Predict Now"):
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        
        hour = now.hour
        dayofyear = now.timetuple().tm_yday
        
        temp, cloud = fetch_current_weather()
        
        irr = predict_core(temp, hour, dayofyear, cloud)
        
        st.metric("Predicted Irradiance (W/m^2)", f"{irr:.2f}")
        
        st.write({
            "Temperature (C)": temp,
            "Cloud Cover (%)": cloud,
            "Hour": hour
        })

# =========================
# MODE 2: HISTORICAL
# =========================
elif mode == "Historical":
    date = st.date_input("Select Date")
    hour = st.slider("Select Hour", 0, 23, 12)
    
    if st.button("Predict Historical"):
        date_str = date.strftime("%Y-%m-%d")
        
        temp, cloud = fetch_past_weather(date_str, hour)
        
        dt = datetime.fromisoformat(f"{date_str}T{hour:02d}:00")
        dayofyear = dt.timetuple().tm_yday
        
        irr = predict_core(temp, hour, dayofyear, cloud)
        
        st.metric("Predicted Irradiance (W/m^2)", f"{irr:.2f}")
        
        st.write({
            "Temperature (C)": temp,
            "Cloud Cover (%)": cloud
        })
        
        st.subheader("Daily Solar Curve")
        df = generate_day_curve(date_str)
        st.line_chart(df.set_index("hour"))

# =========================
# MODE 3: MANUAL
# =========================
elif mode == "Manual":
    date = st.date_input("Select Date")
    hour = st.slider("Select Hour", 0, 23, 12)
    temp = st.number_input("Temperature (C)", value=30.0)
    cloud = st.slider("Cloud Cover (%)", 0, 100, 20)
    
    if st.button("Predict Manual"):
        date_str = date.strftime("%Y-%m-%d")
        
        dt = datetime.fromisoformat(f"{date_str}T{hour:02d}:00")
        dayofyear = dt.timetuple().tm_yday
        
        irr = predict_core(temp, hour, dayofyear, cloud)
        
        st.metric("Predicted Irradiance (W/m^2)", f"{irr:.2f}")
