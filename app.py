import os
import json
import base64
import requests
import uuid
from functools import wraps
from io import BytesIO
from datetime import datetime, date
import time

from PIL import Image
from flask import Flask, render_template, request, jsonify, redirect, session, url_for
from flask_cors import CORS
from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types

# ============================================================
# ENVIRONMENT & APP CONFIG
# ============================================================

load_dotenv()

app = Flask(
    __name__,
    static_folder="static",
    template_folder="templates"
)
CORS(app)

def env_value(name, default=None):
    value = os.getenv(name, default)
    return value.strip().strip('"').strip("'") if isinstance(value, str) else value

app.secret_key = env_value("FLASK_SECRET_KEY", "change-this-secret-before-production")
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")

GEMINI_KEY = env_value("GEMINI_API_KEY")
DATAGOV_KEY = env_value("DATAGOV_API_KEY")
SUPABASE_URL = env_value("SUPABASE_URL")
SUPABASE_KEY = env_value("SUPABASE_KEY")
GEMINI_MODEL = env_value("GEMINI_MODEL", "gemini-3.6-flash")

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_SEASONAL_URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
INDIA_BOUNDS = {"min_lat": 6.0, "max_lat": 37.5, "min_lon": 68.0, "max_lon": 98.0}
WEATHER_CACHE_TTL_SECONDS = 600
WEATHER_CACHE = {}
MANDI_CACHE_TTL_SECONDS = 900
MANDI_CACHE = {}

# ============================================================
# CLIENTS
# ============================================================

supabase: Client = (
    create_client(SUPABASE_URL, SUPABASE_KEY)
    if SUPABASE_URL and SUPABASE_KEY
    else None
)

gemini_client = (
    genai.Client(
        api_key=GEMINI_KEY,
        http_options=types.HttpOptions(
            timeout=120000,
            retry_options=types.HttpRetryOptions(attempts=2)
        )
    )
    if GEMINI_KEY
    else None
)

# ============================================================
# COMPREHENSIVE MANDI DATABASE & BENCHMARKS
# ============================================================

MANDI_FALLBACK_DATABASE = [
    {"state": "Uttar Pradesh", "district": "Agra", "market": "Agra Mandi", "commodity": "Potato", "variety": "Desi / Local", "min_price": 1250, "max_price": 1650, "modal_price": 1480, "arrival_date": "2026-08-30", "expected_yield_per_acre_kg": 9000},
    {"state": "Uttar Pradesh", "district": "Agra", "market": "Fatehabad", "commodity": "Tomato", "variety": "Hybrid Red", "min_price": 1800, "max_price": 2600, "modal_price": 2200, "arrival_date": "2026-08-31", "expected_yield_per_acre_kg": 11000},
    {"state": "Uttar Pradesh", "district": "Aligarh", "market": "Aligarh Mandi", "commodity": "Wheat", "variety": "Sharbati / Desi", "min_price": 2350, "max_price": 2650, "modal_price": 2480, "arrival_date": "2026-08-28", "expected_yield_per_acre_kg": 1900},
    {"state": "Uttar Pradesh", "district": "Mathura", "market": "Mathura Mandi", "commodity": "Mustard", "variety": "Pusa Bold", "min_price": 5200, "max_price": 5750, "modal_price": 5450, "arrival_date": "2026-08-25", "expected_yield_per_acre_kg": 850},
    {"state": "Maharashtra", "district": "Nashik", "market": "Lasalgaon", "commodity": "Onion", "variety": "Red Garwa", "min_price": 1700, "max_price": 2550, "modal_price": 2150, "arrival_date": "2026-08-31", "expected_yield_per_acre_kg": 8500},
    {"state": "Maharashtra", "district": "Pune", "market": "Pune APMC", "commodity": "Soybean", "variety": "Yellow", "min_price": 4200, "max_price": 4750, "modal_price": 4500, "arrival_date": "2026-08-29", "expected_yield_per_acre_kg": 1000},
    {"state": "Maharashtra", "district": "Nagpur", "market": "Nagpur Mandi", "commodity": "Cotton", "variety": "Medium Staple", "min_price": 6800, "max_price": 7500, "modal_price": 7200, "arrival_date": "2026-08-27", "expected_yield_per_acre_kg": 900},
    {"state": "Punjab", "district": "Ludhiana", "market": "Ludhiana Mandi", "commodity": "Wheat", "variety": "PBW 550", "min_price": 2300, "max_price": 2550, "modal_price": 2420, "arrival_date": "2026-08-29", "expected_yield_per_acre_kg": 2000},
    {"state": "Punjab", "district": "Jalandhar", "market": "Jalandhar APMC", "commodity": "Paddy (Basmati)", "variety": "Pusa 1121", "min_price": 3600, "max_price": 4150, "modal_price": 3900, "arrival_date": "2026-08-30", "expected_yield_per_acre_kg": 1700},
    {"state": "Punjab", "district": "Amritsar", "market": "Amritsar APMC", "commodity": "Maize", "variety": "Yellow Hybrid", "min_price": 1950, "max_price": 2300, "modal_price": 2100, "arrival_date": "2026-08-26", "expected_yield_per_acre_kg": 2400},
    {"state": "Madhya Pradesh", "district": "Indore", "market": "Indore Mandi", "commodity": "Soybean", "variety": "JS 9560", "min_price": 4300, "max_price": 4850, "modal_price": 4600, "arrival_date": "2026-08-30", "expected_yield_per_acre_kg": 950},
    {"state": "Madhya Pradesh", "district": "Ujjain", "market": "Ujjain APMC", "commodity": "Gram (Chana)", "variety": "Desi", "min_price": 5400, "max_price": 6100, "modal_price": 5800, "arrival_date": "2026-08-28", "expected_yield_per_acre_kg": 800},
    {"state": "Rajasthan", "district": "Jaipur", "market": "Jaipur (Surajpole)", "commodity": "Mustard", "variety": "Mustard Seed", "min_price": 5300, "max_price": 5800, "modal_price": 5550, "arrival_date": "2026-08-30", "expected_yield_per_acre_kg": 850},
    {"state": "Rajasthan", "district": "Bikaner", "market": "Bikaner Mandi", "commodity": "Moong (Green Gram)", "variety": "Medium", "min_price": 7200, "max_price": 8400, "modal_price": 7900, "arrival_date": "2026-08-27", "expected_yield_per_acre_kg": 450},
    {"state": "Gujarat", "district": "Rajkot", "market": "Rajkot APMC", "commodity": "Groundnut", "variety": "G-20", "min_price": 5900, "max_price": 6700, "modal_price": 6350, "arrival_date": "2026-08-31", "expected_yield_per_acre_kg": 1100},
    {"state": "Gujarat", "district": "Unjha", "market": "Unjha APMC", "commodity": "Cumin (Jeera)", "variety": "Machine Clean", "min_price": 24000, "max_price": 28500, "modal_price": 26500, "arrival_date": "2026-08-30", "expected_yield_per_acre_kg": 380},
    {"state": "Haryana", "district": "Karnal", "market": "Karnal Mandi", "commodity": "Paddy (Basmati)", "variety": "Basmati Traditional", "min_price": 3800, "max_price": 4400, "modal_price": 4150, "arrival_date": "2026-08-31", "expected_yield_per_acre_kg": 1600},
    {"state": "Bihar", "district": "Gulabbagh", "market": "Purnea Mandi", "commodity": "Maize", "variety": "Yellow Hybrid", "min_price": 2050, "max_price": 2350, "modal_price": 2220, "arrival_date": "2026-08-28", "expected_yield_per_acre_kg": 2800}
]

DATA_STORE = [] # Starts empty to rely on Supabase

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def unit_to_kg(quantity: float, unit: str) -> float:
    u = (unit or "kg").lower()
    if "quintal" in u or "कुंतल" in u:
        return quantity * 100.0
    if "ton" in u or "टन" in u:
        return quantity * 1000.0
    return quantity

def decode_image(image_base64):
    try:
        if not image_base64 or "," not in image_base64:
            return None
        _, encoded = image_base64.split(",", 1)
        img_data = base64.b64decode(encoded)
        return Image.open(BytesIO(img_data))
    except Exception as e:
        print(f"Image decode error: {e}")
        return None

def weather_description(weather_code):
    descriptions = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
        96: "Thunderstorm with slight hail",
        99: "Thunderstorm with heavy hail"
    }
    return descriptions.get(int(weather_code or 0), "Weather data available")

def weather_alerts(current, daily):
    """Create advisory flags, not official IMD warnings, from forecast signals."""
    alerts = []
    weather_code = int(current.get("weather_code") or 0)
    wind_speed = safe_float(current.get("wind_speed_10m"))
    temperature = safe_float(current.get("temperature_2m"))
    rain_today = safe_float((daily.get("rain_sum") or [0])[0])
    precipitation_today = safe_float((daily.get("precipitation_sum") or [0])[0])

    if weather_code in {65, 82, 95, 96, 99} or rain_today >= 20 or precipitation_today >= 30:
        alerts.append({"level": "high", "message": "Heavy rain or storm possible. Protect harvested produce and avoid spraying."})
    elif weather_code in {61, 63, 80, 81} or rain_today >= 5:
        alerts.append({"level": "medium", "message": "Rain possible. Check field drainage before irrigation."})
    if wind_speed >= 40:
        alerts.append({"level": "high", "message": "High wind risk. Secure seedlings, shade nets, and loose farm equipment."})
    if temperature <= 2:
        alerts.append({"level": "high", "message": "Frost risk. Protect sensitive seedlings and flowering crops overnight."})
    return alerts

def reverse_geocode_india(latitude, longitude):
    """Resolve a coordinate to a district using Nominatim's free reverse lookup."""
    try:
        response = requests.get(
            NOMINATIM_REVERSE_URL,
            params={"lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 10, "addressdetails": 1},
            headers={"User-Agent": "KrishiSahayak/1.0 (student agriculture project)"},
            timeout=3.0
        )
        response.raise_for_status()
        address = response.json().get("address", {})
        return {
            "district": address.get("state_district") or address.get("county"),
            "state": address.get("state"),
            "country": address.get("country"),
            "display_name": response.json().get("display_name"),
            "source": "OpenStreetMap Nominatim"
        }
    except (requests.RequestException, ValueError, TypeError):
        return {"district": None, "state": None, "country": "India", "display_name": None, "source": None}

# ============================================================
# ROUTES
# ============================================================

def current_user():
    return session.get("user")

def require_auth(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user():
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("auth_page"))
        return view(*args, **kwargs)
    return wrapped_view

def user_batches(user_id):
    if supabase:
        try:
            result = supabase.table("produce_batches").select("*").eq("farmer_id", user_id).order("created_at", desc=True).execute()
            return result.data or []
        except Exception as error:
            app.logger.warning("Could not load user batches: %s", error)
    return [batch for batch in DATA_STORE if batch.get("farmer_id") == user_id]

def default_profile(user):
    return {"farmer_id": user["id"], "full_name": "", "latitude": None, "longitude": None, "location_name": ""}

def load_profile(user):
    profile = default_profile(user)
    if supabase:
        try:
            result = supabase.table("farmer_profiles").select("*").eq("farmer_id", user["id"]).limit(1).execute()
            if result.data:
                profile.update(result.data[0])
        except Exception as error:
            app.logger.warning("Could not load farmer profile: %s", error)
    return profile

@app.route("/auth")
def auth_page():
    if current_user():
        return redirect(url_for("home"))
    return render_template("auth.html")

@app.route("/api/auth/register", methods=["POST"])
def register():
    if not supabase:
        return jsonify({"error": "Supabase is not configured on the server."}), 503
    data = request.json or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    full_name = str(data.get("full_name", "")).strip()
    latitude = safe_float(data.get("latitude"), None)
    longitude = safe_float(data.get("longitude"), None)
    if latitude is not None and longitude is not None and not (INDIA_BOUNDS["min_lat"] <= latitude <= INDIA_BOUNDS["max_lat"] and INDIA_BOUNDS["min_lon"] <= longitude <= INDIA_BOUNDS["max_lon"]):
        return jsonify({"error": "Farm coordinates must be within India."}), 400
    if not email or len(password) < 6:
        return jsonify({"error": "Enter a valid email and a password of at least 6 characters."}), 400
    try:
        result = supabase.auth.sign_up({"email": email, "password": password})
        user = getattr(result, "user", None)
        auth_session = getattr(result, "session", None)
        if not user:
            return jsonify({"error": "Registration could not be completed."}), 400
        try:
            supabase.table("farmer_profiles").upsert({"farmer_id": user.id, "full_name": full_name, "latitude": latitude, "longitude": longitude}).execute()
        except Exception as error:
            app.logger.warning("Could not create farmer profile: %s", error)
        if not auth_session:
            return jsonify({"message": "Account created. Check your email to confirm it, then log in."})
        session["user"] = {"id": user.id, "email": user.email}
        return jsonify({"success": True, "user": session["user"]})
    except Exception as error:
        return jsonify({"error": str(error)}), 400

@app.route("/api/auth/login", methods=["POST"])
def login():
    if not supabase:
        return jsonify({"error": "Supabase is not configured on the server."}), 503
    data = request.json or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    try:
        result = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user = getattr(result, "user", None)
        if not user:
            return jsonify({"error": "Login failed. Check your email and password."}), 401
        session["user"] = {"id": user.id, "email": user.email}
        profile = load_profile(session["user"])
        if profile.get("full_name"):
            session["user"]["full_name"] = profile["full_name"]
        return jsonify({"success": True, "user": session["user"]})
    except Exception:
        return jsonify({"error": "Login failed. Check your email and password."}), 401

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/")
@require_auth
def home():
    return render_template("index.html")

@app.route("/api/profile", methods=["GET", "PUT", "DELETE"])
@require_auth
def profile():
    user = current_user()
    if request.method == "GET":
        return jsonify({"success": True, "profile": load_profile(user)})
    if request.method == "DELETE":
        if supabase:
            try:
                supabase.table("farmer_profiles").delete().eq("farmer_id", user["id"]).execute()
                supabase.table("produce_batches").delete().eq("farmer_id", user["id"]).execute()
            except Exception as error:
                app.logger.exception("Could not delete farmer-owned data")
                return jsonify({"success": False, "error": str(error)}), 502
        session.clear()
        return jsonify({"success": True})

    data = request.json or {}
    full_name = str(data.get("full_name", "")).strip()
    latitude = safe_float(data.get("latitude"), None)
    longitude = safe_float(data.get("longitude"), None)
    if latitude is None or longitude is None:
        return jsonify({"success": False, "error": "Enter both latitude and longitude."}), 400
    if not (INDIA_BOUNDS["min_lat"] <= latitude <= INDIA_BOUNDS["max_lat"] and INDIA_BOUNDS["min_lon"] <= longitude <= INDIA_BOUNDS["max_lon"]):
        return jsonify({"success": False, "error": "Farm coordinates must be within India."}), 400
    location_name = str(data.get("location_name", "")).strip()
    updated = {"farmer_id": user["id"], "full_name": full_name, "latitude": latitude, "longitude": longitude, "location_name": location_name, "updated_at": datetime.utcnow().isoformat()}
    if supabase:
        try:
            result = supabase.table("farmer_profiles").upsert(updated).execute()
            profile_data = result.data[0] if result.data else updated
        except Exception as error:
            return jsonify({"success": False, "error": f"Profile could not be saved: {error}"}), 502
    else:
        profile_data = updated
    session["user"]["full_name"] = full_name
    return jsonify({"success": True, "profile": profile_data})

@app.route("/api/weather", methods=["GET"])
def get_weather():
    """Return India-local weather and agronomic indicators from Open-Meteo."""
    latitude = safe_float(request.args.get("latitude"), None)
    longitude = safe_float(request.args.get("longitude"), None)
    if latitude is None or longitude is None:
        return jsonify({"success": False, "error": "latitude and longitude are required."}), 400
    if not (
        INDIA_BOUNDS["min_lat"] <= latitude <= INDIA_BOUNDS["max_lat"]
        and INDIA_BOUNDS["min_lon"] <= longitude <= INDIA_BOUNDS["max_lon"]
    ):
        return jsonify({"success": False, "error": "Coordinates must be within India."}), 400

    cache_key = (round(latitude, 3), round(longitude, 3))
    cached = WEATHER_CACHE.get(cache_key)
    if cached and time.time() - cached["stored_at"] < WEATHER_CACHE_TTL_SECONDS:
        response_data = dict(cached["data"])
        response_data["cached"] = True
        return jsonify(response_data)

    base_params = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": "Asia/Kolkata",
        "forecast_days": 3,
        "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code,precipitation,rain,shortwave_radiation,direct_normal_irradiance",
        "daily": "weather_code,precipitation_sum,rain_sum,et0_fao_evapotranspiration"
    }
    try:
        response = requests.get(OPEN_METEO_FORECAST_URL, params=base_params, timeout=12.0)
        response.raise_for_status()
        payload = response.json()
        current = payload.get("current", {})
        current_units = payload.get("current_units", {})
        daily = payload.get("daily", {})
        daily_units = payload.get("daily_units", {})
        hourly = {}
        try:
            soil_response = requests.get(
                OPEN_METEO_FORECAST_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": "Asia/Kolkata",
                    "forecast_days": 1,
                    "hourly": "soil_temperature_6cm,soil_moisture_3_to_9cm,shortwave_radiation,direct_normal_irradiance"
                },
                timeout=12.0
            )
            soil_response.raise_for_status()
            hourly = soil_response.json().get("hourly", {})
        except requests.RequestException as error:
            app.logger.warning("Open-Meteo soil/solar hourly request failed: %s", error)
        hourly_index = {time: index for index, time in enumerate(hourly.get("time", []))}
        current_hour = current.get("time")
        soil_index = hourly_index.get(current_hour, 0)

        def hourly_value(name):
            values = hourly.get(name, [])
            return values[soil_index] if soil_index < len(values) else None

        forecast = []
        for index, forecast_date in enumerate(daily.get("time", [])):
            code = (daily.get("weather_code") or [])[index]
            forecast.append({
                "date": forecast_date,
                "weather_code": code,
                "condition": weather_description(code),
                "rainfall_mm": (daily.get("rain_sum") or [])[index],
                "precipitation_mm": (daily.get("precipitation_sum") or [])[index],
                "et0_mm": (daily.get("et0_fao_evapotranspiration") or [])[index]
            })

        response_data = {
            "success": True,
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": payload.get("timezone", "Asia/Kolkata"),
                **reverse_geocode_india(latitude, longitude)
            },
            "observed_at": current_hour,
            "current": {
                "temperature_c": current.get("temperature_2m"),
                "relative_humidity_percent": current.get("relative_humidity_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "rainfall_mm": current.get("rain"),
                "precipitation_mm": current.get("precipitation"),
                "shortwave_radiation_w_m2": current.get("shortwave_radiation"),
                "direct_normal_irradiance_w_m2": current.get("direct_normal_irradiance"),
                "weather_code": current.get("weather_code"),
                "condition": weather_description(current.get("weather_code")),
                "units": {
                    "temperature": current_units.get("temperature_2m", "°C"),
                    "humidity": current_units.get("relative_humidity_2m", "%"),
                    "wind_speed": current_units.get("wind_speed_10m", "km/h"),
                    "solar_radiation": current_units.get("shortwave_radiation", "W/m²"),
                    "direct_normal_irradiance": current_units.get("direct_normal_irradiance", "W/m²")
                }
            },
            "agronomy": {
                "et0_mm": forecast[0]["et0_mm"] if forecast else None,
                "et0_unit": daily_units.get("et0_fao_evapotranspiration", "mm"),
                "soil_temperature_6cm_c": hourly_value("soil_temperature_6cm"),
                "soil_moisture_3_to_9cm_m3_m3": hourly_value("soil_moisture_3_to_9cm"),
                "shortwave_radiation_w_m2": hourly_value("shortwave_radiation"),
                "direct_normal_irradiance_w_m2": hourly_value("direct_normal_irradiance"),
                "soil_moisture_note": "Volumetric water content for the 3-9 cm root zone"
            },
            "forecast": forecast,
            "alerts": weather_alerts(current, daily),
            "alerts_note": "Advisory rules based on Open-Meteo data; not official IMD warnings.",
            "source": "Open-Meteo"
        }
        WEATHER_CACHE[cache_key] = {"stored_at": time.time(), "data": response_data}
        return jsonify(response_data)
    except requests.RequestException as error:
        app.logger.warning("Open-Meteo request failed: %s", error)
        if cached:
            response_data = dict(cached["data"])
            response_data["cached"] = True
            response_data["stale"] = True
            return jsonify(response_data)
        if isinstance(error, requests.HTTPError) and error.response is not None and error.response.status_code == 429:
            return jsonify({"success": False, "error": "Open-Meteo is rate-limiting requests. Please wait a minute and try again."}), 429
        return jsonify({"success": False, "error": "Weather service is temporarily unavailable. Please retry in a few seconds."}), 502
    except (KeyError, IndexError, TypeError, ValueError) as error:
        app.logger.exception("Unexpected Open-Meteo response")
        return jsonify({"success": False, "error": f"Could not read weather data: {type(error).__name__}"}), 502

@app.route("/api/weather/seasonal", methods=["GET"])
def get_seasonal_weather():
    """Return monthly precipitation trends from Open-Meteo's seasonal ensemble."""
    latitude = safe_float(request.args.get("latitude"), None)
    longitude = safe_float(request.args.get("longitude"), None)
    if latitude is None or longitude is None:
        return jsonify({"success": False, "error": "latitude and longitude are required."}), 400
    if not (INDIA_BOUNDS["min_lat"] <= latitude <= INDIA_BOUNDS["max_lat"] and INDIA_BOUNDS["min_lon"] <= longitude <= INDIA_BOUNDS["max_lon"]):
        return jsonify({"success": False, "error": "Coordinates must be within India."}), 400

    try:
        response = requests.get(
            OPEN_METEO_SEASONAL_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "timezone": "Asia/Kolkata",
                "monthly": "precipitation_mean,temperature_2m_mean"
            },
            timeout=15.0
        )
        response.raise_for_status()
        payload = response.json()
        monthly = payload.get("monthly", {})
        precipitation = monthly.get("precipitation_mean", [])
        temperatures = monthly.get("temperature_2m_mean", [])
        months = monthly.get("time", [])
        return jsonify({
            "success": True,
            "location": {"latitude": latitude, "longitude": longitude, "timezone": payload.get("timezone", "Asia/Kolkata")},
            "monthly": [
                {"month": months[index], "precipitation_mm": precipitation[index], "temperature_c": temperatures[index]}
                for index in range(min(len(months), len(precipitation), len(temperatures)))
            ],
            "source": "Open-Meteo Seasonal API"
        })
    except requests.RequestException as error:
        app.logger.warning("Open-Meteo seasonal request failed: %s", error)
        return jsonify({"success": False, "error": "Seasonal forecast is temporarily unavailable."}), 502
    except (KeyError, IndexError, TypeError, ValueError) as error:
        return jsonify({"success": False, "error": f"Could not read seasonal data: {type(error).__name__}"}), 502

@app.route("/api/produce/list", methods=["GET"])
@require_auth
def list_produce():
    user = current_user()
    if supabase:
        try:
            res = supabase.table("produce_batches").select("*").eq("farmer_id", user["id"]).order("created_at", desc=True).execute()
            if hasattr(res, 'data'):
                # Sync local store with Supabase
                global DATA_STORE
                DATA_STORE = res.data
                return jsonify({"success": True, "batches": res.data})
        except Exception as e:
            print(f"Supabase error: {e}")
    
    local = [b for b in DATA_STORE if b.get("farmer_id") == user["id"]]
    return jsonify({"success": True, "batches": local})

@app.route("/api/produce/delete-all", methods=["DELETE"])
@require_auth
def delete_all_produce():
    user = current_user()
    if not supabase:
        return jsonify({"success": False, "error": "Supabase is not configured on the server."}), 503
    try:
        supabase.table("produce_batches").delete().eq("farmer_id", user["id"]).execute()
        global DATA_STORE
        DATA_STORE = [batch for batch in DATA_STORE if batch.get("farmer_id") != user["id"]]
        return jsonify({"success": True})
    except Exception as error:
        app.logger.exception("Could not delete user crop data")
        return jsonify({"success": False, "error": f"Could not delete crop data: {error}"}), 502

@app.route("/api/produce/analyze-and-add", methods=["POST"])
@require_auth
def analyze_and_add_produce():
    try:
        data = request.json or {}
        user = current_user()
        crop_name = str(data.get("crop_name", "Produce")).strip()
        variety = str(data.get("variety", "Desi / Local")).strip()
        field_name = str(data.get("field_name", "Field 1")).strip()
        raw_quantity = safe_float(data.get("quantity", 100), 100)
        unit = data.get("unit", "kg")
        quantity_kg = unit_to_kg(raw_quantity, unit)
        harvest_date = data.get("harvest_date", datetime.today().strftime("%Y-%m-%d"))
        storage_type = data.get("storage_type", "Ventilated Godown")
        image_base64 = data.get("image_base64")
        costs = data.get("production_costs", {})
        production_cost = sum(safe_float(v) for v in costs.values())

        quality_grade = "A"
        spoilage_risk = "Low"
        shelf_life_days = 14
        defects = "Clean surface; uniform maturity."
        recommendation = "Maintain regular ventilation and store in a cool, dry area."
        processing_idea = "Standard wholesale grading and sorting."

        if gemini_client:
            prompt = f"""
Analyze post-harvest crop quality:
- Crop: {crop_name}, Variety: {variety}, Field: {field_name}
- Quantity: {quantity_kg} kg, Harvest Date: {harvest_date}, Storage: {storage_type}

Respond strictly in valid JSON:
{{
    "quality_grade": "A" or "B" or "C",
    "defect_summary": "Concise physical/visual defect summary",
    "spoilage_risk": "Low" or "Medium" or "High",
    "shelf_life_days": integer_days_remaining,
    "recommendation": "Storage instructions",
    "processing_idea": "Value-addition/processing idea"
}}
"""
            contents = [prompt]
            img = decode_image(image_base64)
            if img:
                contents.append(img)
            try:
                response = gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        max_output_tokens=256,
                        thinking_config=types.ThinkingConfig(thinking_level="low")
                    )
                )
                if response.text:
                    ai_res = json.loads(response.text)
                    quality_grade = ai_res.get("quality_grade", quality_grade)
                    defects = ai_res.get("defect_summary", defects)
                    spoilage_risk = ai_res.get("spoilage_risk", spoilage_risk)
                    shelf_life_days = int(ai_res.get("shelf_life_days", shelf_life_days))
                    recommendation = ai_res.get("recommendation", recommendation)
                    processing_idea = ai_res.get("processing_idea", processing_idea)
            except Exception as e:
                print(f"Gemini quality error: {e}")

        new_batch = {
            "id": str(uuid.uuid4()),
            "farmer_id": user["id"],
            "farmer_phone": user["email"],
            "crop_name": crop_name,
            "variety": variety,
            "field_name": field_name,
            "quantity_kg": quantity_kg,
            "input_unit": unit,
            "harvest_date": harvest_date,
            "storage_type": storage_type,
            "quality_grade": quality_grade,
            "spoilage_risk": spoilage_risk,
            "shelf_life_days": shelf_life_days,
            "defect_summary": defects,
            "recommendation": recommendation,
            "processing_idea": processing_idea,
            "production_cost": production_cost,
            "cost_breakdown": costs,
            "status": "active",
            "sold_quantity_kg": 0,
            "selling_price_per_kg": 0,
            "selling_date": None,
            "selling_costs_breakdown": {},
            "total_selling_cost": 0,
            "total_combined_cost": production_cost,
            "total_revenue": 0,
            "net_profit_loss": 0,
            "next_crop_recommendation": []
        }

        if not supabase:
            return jsonify({"success": False, "error": "Supabase is not configured on the server."}), 503
        res = supabase.table("produce_batches").insert(new_batch).execute()
        if not getattr(res, "data", None):
            return jsonify({"success": False, "error": "Crop could not be saved to Supabase."}), 502
        new_batch = res.data[0]
        DATA_STORE.insert(0, new_batch)
        return jsonify({"success": True, "batch": new_batch})
    except Exception as e:
        app.logger.exception("Crop registration failed")
        return jsonify({"success": False, "error": f"Crop could not be saved: {type(e).__name__}: {e}"}), 500

@app.route("/api/produce/settle-sale", methods=["POST"])
@require_auth
def settle_sale():
    try:
        data = request.json or {}
        batch_id = data.get("batch_id")
        sold_qty = safe_float(data.get("sold_quantity_kg", 0))
        selling_price_per_kg = safe_float(data.get("selling_price_per_kg", 0))
        selling_date = data.get("selling_date", datetime.today().strftime("%Y-%m-%d"))
        selling_costs = data.get("selling_costs", {})
        total_selling_cost = sum(safe_float(v) for v in selling_costs.values())

        user = current_user()
        batch = next((b for b in user_batches(user["id"]) if str(b["id"]) == str(batch_id)), None)
        if not batch:
            return jsonify({"success": False, "error": "Batch not found"}), 404

        prod_cost = safe_float(batch.get("production_cost", 0))
        combined_cost = prod_cost + total_selling_cost
        revenue = sold_qty * selling_price_per_kg
        net_pl = revenue - combined_cost

        next_crop_plans = []
        if gemini_client:
            prompt = f"""
Farmer sold: {batch.get('crop_name')} ({batch.get('variety')}) from field: {batch.get('field_name')}.
Combined Cost: Rs {combined_cost}, Revenue: Rs {revenue}, Net Profit: Rs {net_pl}.
Recommend 2 optimal crop rotation plans in valid JSON:
[
  {{
    "crop": "Crop Name",
    "reason": "Agronomic & soil restoration reason in 2 sentences.",
    "roi_potential": "High/Medium",
    "water_need": "Low/Medium/High"
  }}
]
"""
            try:
                rec_res = gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        max_output_tokens=256,
                        thinking_config=types.ThinkingConfig(thinking_level="low")
                    )
                )
                if rec_res.text:
                    next_crop_plans = json.loads(rec_res.text)
            except Exception as e:
                print(f"Gemini rotation error: {e}")

        batch.update({
            "status": "sold",
            "sold_quantity_kg": sold_qty,
            "selling_price_per_kg": selling_price_per_kg,
            "selling_date": selling_date,
            "selling_costs_breakdown": selling_costs,
            "total_selling_cost": total_selling_cost,
            "total_combined_cost": combined_cost,
            "total_revenue": revenue,
            "net_profit_loss": net_pl,
            "next_crop_recommendation": next_crop_plans
        })

        if supabase:
            try:
                supabase.table("produce_batches").update(batch).eq("id", batch_id).execute()
            except Exception as e:
                print(f"Supabase update error: {e}")

        return jsonify({"success": True, "batch": batch})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# MULTI-ENDPOINT MANDI RATES API
# ============================================================

@app.route("/api/market/mandi-rates", methods=["GET"])
def get_mandi_rates():
    commodity = request.args.get("commodity", "").strip()
    state = request.args.get("state", "").strip()
    district = request.args.get("district", "").strip()
    today_str = date.today().strftime("%Y-%m-%d")
    cache_key = (commodity.lower(), state.lower(), district.lower())
    cached = MANDI_CACHE.get(cache_key)
    if cached and time.time() - cached["stored_at"] < MANDI_CACHE_TTL_SECONDS:
        response_data = dict(cached["data"])
        response_data["cached"] = True
        return jsonify(response_data)

    records = []
    source = "fallback_cache"

    if DATAGOV_KEY:
        try:
            endpoint = "9ef84268-d588-465a-a308-a864a43d0070"
            url = (
                f"https://api.data.gov.in/resource/{endpoint}"
                f"?api-key={DATAGOV_KEY}"
                "&format=json"
                "&limit=100"
            )
            if state:
                url += f"&filters[state]={state}"
            if commodity:
                url += f"&filters[commodity]={commodity}"

            resp = requests.get(url, timeout=8.0)
            gov_records = resp.json().get("records", []) if resp.status_code == 200 else []

            if gov_records:
                # Remove duplicates so farmers don't see the exact same crop twice
                unique_records = {}
                for r in gov_records:
                    sig = f"{r.get('state')}_{r.get('market')}_{r.get('commodity')}_{r.get('variety')}"
                    if sig not in unique_records:
                        unique_records[sig] = r

                for r in unique_records.values():
                    arr_date = r.get("arrival_date", today_str)
                    is_today = (arr_date == today_str)
                    records.append({
                        "state": r.get("state", ""),
                        "district": r.get("district", ""),
                        "market": r.get("market", ""),
                        "commodity": r.get("commodity", ""),
                        "variety": r.get("variety", "General"),
                        "min_price": safe_float(r.get("min_price", 0)),
                        "max_price": safe_float(r.get("max_price", 0)),
                        "modal_price": safe_float(r.get("modal_price", 0)),
                        "arrival_date": arr_date,
                        "is_today": is_today,
                        "price_type": "Live APMC Data" if is_today else "Latest Recorded Mandi Rate"
                    })
                source = "live_datagov"
        except Exception as e:
            print(f"Data.gov API fetch error: {e}")

    # Fallback Data Execution
    if not records:
        filtered = MANDI_FALLBACK_DATABASE
        if commodity:
            filtered = [f for f in filtered if commodity.lower() in f["commodity"].lower()]
        if state:
            filtered = [f for f in filtered if state.lower() in f["state"].lower()]
        if district:
            filtered = [f for f in filtered if district.lower() in f["district"].lower()]

        for r in filtered:
            arr_date = r.get("arrival_date", "2026-08-30")
            records.append({
                "state": r["state"],
                "district": r["district"],
                "market": r["market"],
                "commodity": r["commodity"],
                "variety": r["variety"],
                "min_price": r["min_price"],
                "max_price": r["max_price"],
                "modal_price": r["modal_price"],
                "arrival_date": arr_date,
                "is_today": (arr_date == today_str),
                "price_type": "Latest Verified Benchmark Rate"
            })

    response_data = {
        "success": True,
        "source": source,
        "source_label": "Live Data.gov.in APMC records" if source == "live_datagov" else "Fallback benchmark records; government API unavailable",
        "total_records": len(records),
        "records": records
    }
    MANDI_CACHE[cache_key] = {"stored_at": time.time(), "data": response_data}
    return jsonify(response_data)

# ============================================================
# PRE-COST / PRODUCTION ESTIMATE API
# ============================================================

@app.route("/api/calculator/pre-cost", methods=["POST"])
def calculate_pre_cost():
    try:
        data = request.json or {}
        crop_name = data.get("crop_name", "Wheat").strip()
        land_area = safe_float(data.get("land_area", 1.0), 1.0)
        area_unit = data.get("area_unit", "Acre").strip()

        acre_multiplier = 1.0
        if "hectare" in area_unit.lower() or "हेक्टेयर" in area_unit.lower():
            acre_multiplier = 2.471
        elif "bigha" in area_unit.lower() or "बीघा" in area_unit.lower():
            acre_multiplier = 0.40

        normalized_acres = land_area * acre_multiplier

        costs = {
            "seeds": safe_float(data.get("cost_seeds", 0)),
            "fertilizer": safe_float(data.get("cost_fertilizer", 0)),
            "pesticide": safe_float(data.get("cost_pesticide", 0)),
            "irrigation": safe_float(data.get("cost_irrigation", 0)),
            "labor": safe_float(data.get("cost_labor", 0)),
            "machinery": safe_float(data.get("cost_machinery", 0)),
            "electricity_fuel": safe_float(data.get("cost_fuel", 0)),
            "misc": safe_float(data.get("cost_misc", 0))
        }
        total_production_cost = sum(costs.values())

        benchmark = next(
            (b for b in MANDI_FALLBACK_DATABASE if crop_name.lower() in b["commodity"].lower()),
            {"modal_price": 2200, "expected_yield_per_acre_kg": 1500, "arrival_date": "2026-08-30"}
        )

        user_yield = safe_float(data.get("custom_yield_kg", 0))
        if user_yield > 0:
            total_expected_yield_kg = user_yield
        else:
            total_expected_yield_kg = benchmark["expected_yield_per_acre_kg"] * normalized_acres

        rate_per_quintal = benchmark["modal_price"]
        rate_per_kg = rate_per_quintal / 100.0

        estimated_revenue = total_expected_yield_kg * rate_per_kg
        expected_profit_loss = estimated_revenue - total_production_cost
        profit_per_acre = expected_profit_loss / normalized_acres if normalized_acres > 0 else 0
        profit_per_selected_unit = expected_profit_loss / land_area if land_area > 0 else 0

        return jsonify({
            "success": True,
            "crop_name": crop_name,
            "land_area": land_area,
            "area_unit": area_unit,
            "total_production_cost": round(total_production_cost, 2),
            "expected_yield_kg": round(total_expected_yield_kg, 2),
            "expected_yield_quintals": round(total_expected_yield_kg / 100.0, 2),
            "mandi_modal_price_per_quintal": rate_per_quintal,
            "mandi_price_per_kg": rate_per_kg,
            "rate_date": benchmark.get("arrival_date", "2026-08-30"),
            "estimated_revenue": round(estimated_revenue, 2),
            "expected_profit_loss": round(expected_profit_loss, 2),
            "profit_per_acre": round(profit_per_acre, 2),
            "profit_per_selected_unit": round(profit_per_selected_unit, 2),
            "cost_breakdown": costs
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================
# AI ASSISTANT CHAT WITH LANGUAGE SUPPORT
# ============================================================

@app.route("/api/assistant/chat", methods=["POST"])
@require_auth
def assistant_chat():
    try:
        data = request.json or {}
        user_message = data.get("message", "").strip()
        image_base64 = data.get("image_base64", None)
        lang = data.get("lang", "en").strip()

        if not gemini_client:
            return jsonify({
                "error": "GEMINI_API_KEY is not configured on the server.",
                "updated_batches": user_batches(current_user()["id"])
            }), 503

        batches_context = json.dumps(user_batches(current_user()["id"]), indent=2, ensure_ascii=False)
        target_lang = "Hindi (हिंदी)" if lang == "hi" else "English"

        system_instruction = f"""
You are KrishiSahayak, an agronomist and financial advisor for Indian farmers.
Always respond strictly in: {target_lang}.

Farmer's Stored Batches Database:
{batches_context}

Capabilities:
1. Explain pre-production costs, yield estimates, and break-even mandi prices.
2. Multimodal: If an image is provided, identify crop defects, plant rot, or diseases.
3. Give complete, clear answers that are easy for a farmer to understand. Prefer 2-5 short paragraphs or a short bullet list when useful.
4. Never stop in the middle of a sentence. Finish the answer before reaching the response limit.
5. If the user asks to modify a batch, add at the bottom:
ACTION_UPDATE: {{"batch_id": "<id>", "storage_type": "<val>", "recommendation": "<val>"}}
"""
        contents = [f"{system_instruction}\n\nUser Question: {user_message}"]
        pil_img = decode_image(image_base64)
        if pil_img:
            contents.append(pil_img)

        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    max_output_tokens=1536,
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                )
            )
            reply_text = response.text or ("कोई उत्तर प्राप्त नहीं हुआ।" if lang == "hi" else "I could not generate a response. Please try again.")
        except Exception as e:
            app.logger.exception("Gemini assistant request failed (model=%s)", GEMINI_MODEL)
            return jsonify({
                "error": f"Gemini request failed: {type(e).__name__}",
                "updated_batches": user_batches(current_user()["id"])
            }), 502

        if "ACTION_UPDATE:" in reply_text:
            try:
                parts = reply_text.split("ACTION_UPDATE:", 1)
                reply_text = parts[0].strip()
                action_data = json.loads(parts[1].strip())
                batch_id = action_data.get("batch_id")
                for b in user_batches(current_user()["id"]):
                    if str(b["id"]) == str(batch_id):
                        for k in ["storage_type", "recommendation"]:
                            if k in action_data:
                                b[k] = action_data[k]
                        if supabase:
                            supabase.table("produce_batches").update({
                                key: action_data[key]
                                for key in ["storage_type", "recommendation"]
                                if key in action_data
                            }).eq("id", batch_id).eq("farmer_id", current_user()["id"]).execute()
            except Exception as parse_err:
                print(f"Action parse error: {parse_err}")

        if not reply_text.strip():
            return jsonify({
                "error": "Gemini returned an empty response.",
                "updated_batches": user_batches(current_user()["id"])
            }), 502

        return jsonify({"reply": reply_text, "updated_batches": user_batches(current_user()["id"])})
    except Exception as e:
        app.logger.exception("Unexpected assistant chat error")
        return jsonify({
            "error": f"Assistant server error: {type(e).__name__}",
            "updated_batches": user_batches(current_user()["id"]) if current_user() else []
        }), 500

# ============================================================
# SERVER START
# ============================================================

if __name__ == "__main__":
    print("================================================")
    print("KrishiSahayak AI Server Starting...")
    print(f"Gemini Model: {GEMINI_MODEL}")
    print(f"Supabase Database Connected: {'YES' if supabase else 'NO'}")
    print("================================================")
    app.run(host="0.0.0.0", port=5000, debug=True)