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
DATAGOV_RESOURCE_ID = env_value("DATAGOV_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070")
DATAGOV_MAX_RESULTS = max(1, min(int(env_value("DATAGOV_MAX_RESULTS", "1000")), 1000))
MANDI_API_URL = env_value("MANDI_API_URL", "https://mandi-api.onrender.com/v1")
MANDI_SUPPORTED_STATES = ("Maharashtra", "Uttar Pradesh", "Punjab", "Madhya Pradesh", "Karnataka")
SECONDARY_MANDI_API_URL = env_value("SECONDARY_MANDI_API_URL")
SECONDARY_AI_KEY = env_value("SECONDARY_AI_API_KEY")
SECONDARY_AI_URL = env_value("SECONDARY_AI_API_URL", "https://api.openai.com/v1/chat/completions")
SECONDARY_AI_MODEL = env_value("SECONDARY_AI_MODEL", "gpt-4o-mini")
SUPABASE_URL = env_value("SUPABASE_URL")
SUPABASE_KEY = env_value("SUPABASE_KEY")
GEMINI_MODEL = env_value("GEMINI_MODEL", "gemini-3.6-flash")
GOOGLE_MAPS_API_KEY = env_value("GOOGLE_MAPS_API_KEY")
STORAGE_SEARCH_RADIUS_METERS = max(50000, min(int(env_value("STORAGE_SEARCH_RADIUS_METERS", "200000")), 1000000))
ADMIN_EMAILS = {
    email.strip().lower()
    for email in env_value("ADMIN_EMAILS", "").split(",")
    if email.strip()
}

ACCUWEATHER_API_KEY = env_value("ACCUWEATHER_API_KEY")
ACCUWEATHER_BASE_URL = "https://dataservice.accuweather.com"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
OVERPASS_API_URL = "https://overpass-api.de/api/interpreter"
INDIA_BOUNDS = {"min_lat": 6.0, "max_lat": 37.5, "min_lon": 68.0, "max_lon": 98.0}
WEATHER_CACHE_TTL_SECONDS = 2700
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

storage_gemini_client = (
    genai.Client(
        api_key=GEMINI_KEY,
        http_options=types.HttpOptions(
            timeout=12000,
            retry_options=types.HttpRetryOptions(attempts=1)
        )
    )
    if GEMINI_KEY
    else None
)

def secondary_ai_response(contents, json_mode=False, max_tokens=512):
    """Call an optional OpenAI-compatible provider after the primary AI fails."""
    if not SECONDARY_AI_KEY:
        return None

    text_parts = [item for item in contents if isinstance(item, str)]
    message_content = [{"type": "text", "text": "\n\n".join(text_parts)}]
    for item in contents:
        if isinstance(item, Image.Image):
            buffer = BytesIO()
            item.save(buffer, format="JPEG")
            message_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64.b64encode(buffer.getvalue()).decode()}"}
            })

    payload = {
        "model": SECONDARY_AI_MODEL,
        "messages": [{"role": "user", "content": message_content}],
        "max_tokens": max_tokens
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    response = requests.post(
        SECONDARY_AI_URL,
        headers={"Authorization": f"Bearer {SECONDARY_AI_KEY}", "Content-Type": "application/json"},
        json=payload,
        timeout=120
    )
    response.raise_for_status()
    choices = response.json().get("choices", [])
    return choices[0].get("message", {}).get("content") if choices else None

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

def fallback_next_crop_plan(crop_name):
    return [
        {
            "crop": "Potato" if crop_name.lower() == "tomato" else "Tomato",
            "reason": "Crop rotation can help maintain soil balance and reduce production risk.",
            "roi_potential": "Medium",
            "water_need": "Medium"
        },
        {
            "crop": "Pulses",
            "reason": "A pulse crop can improve soil nitrogen and reduce input costs for the next cycle.",
            "roi_potential": "Medium",
            "water_need": "Low"
        }
    ]

def fallback_storage_plan(crop_name):
    crop = crop_name.lower()
    if any(item in crop for item in ["potato", "onion", "apple"]):
        return {"storage_type": "Cold storage warehouse", "search_queries": ["cold storage", "refrigerated warehouse"], "reason": "Temperature-controlled storage helps reduce moisture loss and sprouting."}
    if any(item in crop for item in ["tomato", "fruit", "mango", "grape"]):
        return {"storage_type": "Pre-cooling and cold storage facility", "search_queries": ["fruit cold storage", "pre cooling facility", "cold storage"], "reason": "Pre-cooling and controlled temperature can slow ripening and protect quality."}
    if any(item in crop for item in ["wheat", "rice", "paddy", "maize", "gram", "chana", "soybean", "mustard"]):
        return {"storage_type": "Grain warehouse or silo", "search_queries": ["grain warehouse", "agricultural warehouse", "silo"], "reason": "Dry, ventilated grain storage helps control moisture and pests."}
    return {"storage_type": "Agricultural warehouse", "search_queries": ["agricultural warehouse", "farm storage warehouse", "cold storage"], "reason": "A clean, secure agricultural warehouse is a flexible short-term option."}

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

def is_admin(user=None):
    user = user or current_user()
    return bool(user and user.get("email", "").lower() in ADMIN_EMAILS)

def require_admin(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user():
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required."}), 401
            return redirect(url_for("auth_page"))
        if not is_admin():
            if request.path.startswith("/api/"):
                return jsonify({"error": "Admin access is required."}), 403
            return redirect(url_for("home"))
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
    return render_template("index.html", is_admin=is_admin(), google_maps_api_key=GOOGLE_MAPS_API_KEY)

@app.route("/admin")
@require_admin
def admin_dashboard():
    return render_template("admin.html")

@app.route("/api/admin/overview", methods=["GET"])
@require_admin
def admin_overview():
    if not supabase:
        return jsonify({"success": False, "error": "Supabase is not configured on the server."}), 503
    try:
        profiles_result = supabase.table("farmer_profiles").select("*").execute()
        batches_result = supabase.table("produce_batches").select("*").order("created_at", desc=True).execute()
        profiles = profiles_result.data or []
        batches = batches_result.data or []
        profile_map = {profile.get("farmer_id"): profile for profile in profiles}

        farmer_ids = {batch.get("farmer_id") for batch in batches if batch.get("farmer_id")}
        farmer_ids.update(profile_map.keys())
        crop_mix = {}
        state_mix = {}
        risk_mix = {"Low": 0, "Medium": 0, "High": 0, "Not applicable": 0}
        totals = {"active_quantity_kg": 0, "total_quantity_kg": 0, "revenue": 0, "profit": 0, "production_cost": 0}
        recent_batches = []

        for batch in batches:
            crop_name = batch.get("crop_name") or "Unknown crop"
            crop_mix[crop_name] = crop_mix.get(crop_name, 0) + 1
            risk = batch.get("spoilage_risk") or "Not applicable"
            risk_mix[risk] = risk_mix.get(risk, 0) + 1
            quantity = safe_float(batch.get("quantity_kg"))
            totals["total_quantity_kg"] += quantity
            totals["production_cost"] += safe_float(batch.get("production_cost"))
            if batch.get("status") == "active":
                totals["active_quantity_kg"] += quantity
            totals["revenue"] += safe_float(batch.get("total_revenue"))
            totals["profit"] += safe_float(batch.get("net_profit_loss"))

            profile = profile_map.get(batch.get("farmer_id"), {})
            location = profile.get("location_name") or "Location not added"
            state = location.split(",")[-1].strip() if "," in location else location
            if state and state != "Location not added":
                state_mix[state] = state_mix.get(state, 0) + 1
            if len(recent_batches) < 12:
                recent_batches.append({
                    "id": batch.get("id"), "crop_name": crop_name, "status": batch.get("status") or "active",
                    "crop_status": batch.get("crop_status") or "harvested", "quantity_kg": quantity,
                    "spoilage_risk": risk, "created_at": batch.get("created_at"),
                    "farmer_name": profile.get("full_name") or "Unnamed farmer", "location": location,
                })

        farmer_rows = []
        for farmer_id in sorted(farmer_ids):
            profile = profile_map.get(farmer_id, {})
            farmer_batches = [batch for batch in batches if batch.get("farmer_id") == farmer_id]
            farmer_rows.append({
                "farmer_id": farmer_id, "full_name": profile.get("full_name") or "Unnamed farmer",
                "location": profile.get("location_name") or "Location not added", "crop_count": len(farmer_batches),
                "active_quantity_kg": sum(safe_float(batch.get("quantity_kg")) for batch in farmer_batches if batch.get("status") == "active"),
                "revenue": sum(safe_float(batch.get("total_revenue")) for batch in farmer_batches),
                "profit": sum(safe_float(batch.get("net_profit_loss")) for batch in farmer_batches),
                "last_activity": max((batch.get("created_at") for batch in farmer_batches if batch.get("created_at")), default=None),
            })

        return jsonify({
            "success": True, "refreshed_at": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "farmer_count": len(farmer_ids), "profile_count": len(profiles), "batch_count": len(batches),
                "active_batches": sum(1 for batch in batches if batch.get("status") == "active"),
                "sold_batches": sum(1 for batch in batches if batch.get("status") == "sold"),
                "high_risk_batches": risk_mix.get("High", 0), **totals,
            },
            "crop_mix": [{"label": key, "value": value} for key, value in sorted(crop_mix.items(), key=lambda item: item[1], reverse=True)],
            "state_mix": [{"label": key, "value": value} for key, value in sorted(state_mix.items(), key=lambda item: item[1], reverse=True)],
            "risk_mix": [{"label": key, "value": value} for key, value in risk_mix.items() if value],
            "farmers": sorted(farmer_rows, key=lambda row: row["crop_count"], reverse=True),
            "recent_batches": recent_batches,
        })
    except Exception as error:
        app.logger.exception("Could not load admin overview")
        return jsonify({"success": False, "error": f"Could not load admin data: {error}"}), 502

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

def accuweather_time(value):
    if not value:
        return None
    return str(value)[11:16]

def accuweather_rainfall(forecast_day):
    rain = forecast_day.get("Day", {}).get("Rain", {})
    return safe_float(rain.get("Value"), 0.0)

def accuweather_alerts(current, forecast):
    alerts = []
    if current.get("HasPrecipitation") or any(day.get("Day", {}).get("HasPrecipitation") for day in forecast[:1]):
        alerts.append({"level": "medium", "message": "Rain is possible. Check field drainage before irrigation."})
    wind = safe_float(current.get("Wind", {}).get("Speed", {}).get("Metric", {}).get("Value"))
    if wind >= 40:
        alerts.append({"level": "high", "message": "High wind risk. Secure seedlings, shade nets, and loose farm equipment."})
    return alerts

@app.route("/api/weather", methods=["GET"])
def get_weather():
    """Return GPS weather from the official AccuWeather API."""
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

    try:
        if not ACCUWEATHER_API_KEY:
            return jsonify({"success": False, "error": "AccuWeather API is not configured."}), 503
        auth = {"apikey": ACCUWEATHER_API_KEY, "language": "en-us"}
        location_response = requests.get(
            f"{ACCUWEATHER_BASE_URL}/locations/v1/cities/geoposition/search",
            params={**auth, "q": f"{latitude},{longitude}", "details": "false"},
            timeout=12.0
        )
        location_response.raise_for_status()
        location = location_response.json()
        location_key = location.get("Key")
        if not location_key:
            raise ValueError("AccuWeather did not return a location key.")

        current_response = requests.get(
            f"{ACCUWEATHER_BASE_URL}/currentconditions/v1/{location_key}",
            params={**auth, "details": "true"},
            timeout=12.0
        )
        forecast_response = requests.get(
            f"{ACCUWEATHER_BASE_URL}/forecasts/v1/daily/5day/{location_key}",
            params={**auth, "details": "true", "metric": "true"},
            timeout=12.0
        )
        current_response.raise_for_status()
        forecast_response.raise_for_status()
        current = (current_response.json() or [{}])[0]
        forecast_payload = forecast_response.json()
        forecast_days = forecast_payload.get("DailyForecasts", [])
        forecast = []
        for forecast_day in forecast_days:
            day = forecast_day.get("Day", {})
            forecast.append({
                "date": str(forecast_day.get("Date", ""))[:10],
                "condition": day.get("IconPhrase", "Weather data available"),
                "temperature_max_c": forecast_day.get("Temperature", {}).get("Maximum", {}).get("Value"),
                "temperature_min_c": forecast_day.get("Temperature", {}).get("Minimum", {}).get("Value"),
                "precipitation_mm": accuweather_rainfall(forecast_day),
                "rain_probability_percent": day.get("RainProbability", 0),
                "sunrise": accuweather_time(day.get("Sun" , {}).get("Rise")),
                "sunset": accuweather_time(day.get("Sun" , {}).get("Set"))
            })

        response_data = {
            "success": True,
            "location": {
                "latitude": latitude,
                "longitude": longitude,
                "timezone": location.get("TimeZone", {}).get("Name", "")
            },
            "observed_at": current.get("LocalObservationDateTime"),
            "current": {
                "temperature_c": current.get("Temperature", {}).get("Metric", {}).get("Value"),
                "relative_humidity_percent": current.get("RelativeHumidity"),
                "wind_speed_kmh": current.get("Wind", {}).get("Speed", {}).get("Metric", {}).get("Value"),
                "precipitation_mm": current.get("PrecipitationSummary", {}).get("Precipitation", {}).get("Metric", {}).get("Value", 0),
                "rainfall_mm": current.get("PrecipitationSummary", {}).get("Precipitation", {}).get("Metric", {}).get("Value", 0),
                "condition": current.get("WeatherText", "Weather data available"),
                "units": {
                    "temperature": "°C",
                    "humidity": "%",
                    "wind_speed": "km/h",
                    "precipitation": "mm",
                    "rain": "mm"
                }
            },
            "forecast": forecast,
            "alerts": accuweather_alerts(current, forecast_days),
            "source": "AccuWeather"
        }
        WEATHER_CACHE[cache_key] = {"stored_at": time.time(), "data": response_data}
        return jsonify(response_data)
    except requests.RequestException as error:
        app.logger.warning("AccuWeather request failed: %s", error)
        if cached:
            response_data = dict(cached["data"])
            response_data["cached"] = True
            response_data["stale"] = True
            return jsonify(response_data)
        return jsonify({"success": False, "error": "AccuWeather is temporarily unavailable. Please try again."}), 502
    except (KeyError, IndexError, TypeError, ValueError) as error:
        app.logger.exception("Unexpected AccuWeather response")
        return jsonify({"success": False, "error": "Could not read AccuWeather data. Please try again."}), 502

@app.route("/api/storage/search", methods=["GET"])
@require_auth
def search_storage_facilities():
    """Find storage-related places through OpenStreetMap when Google Places is unavailable."""
    latitude = safe_float(request.args.get("latitude"), None)
    longitude = safe_float(request.args.get("longitude"), None)
    if latitude is None or longitude is None:
        return jsonify({"success": False, "error": "latitude and longitude are required."}), 400
    if not (
        INDIA_BOUNDS["min_lat"] <= latitude <= INDIA_BOUNDS["max_lat"]
        and INDIA_BOUNDS["min_lon"] <= longitude <= INDIA_BOUNDS["max_lon"]
    ):
        return jsonify({"success": False, "error": "Coordinates must be within India."}), 400

    query = f"""
[out:json][timeout:20];
(
  nwr["name"~"cold|storage|warehouse|godown|grain|agricultur",i](around:60000,{latitude},{longitude});
  nwr["building"~"warehouse|industrial",i](around:60000,{latitude},{longitude});
);
out center tags;
"""
    try:
        response = requests.post(
            OVERPASS_API_URL,
            data=query,
            headers={"User-Agent": "KrishiSahayak/1.0 (student agriculture project)"},
            timeout=25.0,
        )
        response.raise_for_status()
        places = []
        seen = set()
        for element in response.json().get("elements", []):
            tags = element.get("tags", {})
            point = element.get("center", element)
            place_lat = point.get("lat")
            place_lon = point.get("lon")
            name = tags.get("name")
            if not name or place_lat is None or place_lon is None:
                continue
            place_id = f"osm-{element.get('type')}-{element.get('id')}"
            if place_id in seen:
                continue
            seen.add(place_id)
            address = tags.get("addr:full") or ", ".join(
                value for value in [tags.get("addr:street"), tags.get("addr:city"), tags.get("addr:state")] if value
            )
            places.append({
                "place_id": place_id, "name": name, "formatted_address": address,
                "lat": place_lat, "lng": place_lon, "source": "OpenStreetMap",
            })
        return jsonify({"success": True, "places": places})
    except (requests.RequestException, ValueError, TypeError) as error:
        app.logger.warning("Storage fallback search failed: %s", error)
        return jsonify({"success": False, "error": "The storage directory is temporarily unavailable."}), 502

@app.route("/api/storage/recommend", methods=["POST"])
@require_auth
def recommend_storage():
    data = request.json or {}
    crop_name = str(data.get("crop_name", "Produce")).strip() or "Produce"
    variety = str(data.get("variety", "Not specified")).strip()
    quantity_kg = safe_float(data.get("quantity_kg"), 0)
    fallback = fallback_storage_plan(crop_name)
    if not storage_gemini_client and not SECONDARY_AI_KEY:
        return jsonify({"success": True, "source": "rule_based", **fallback})

    prompt = f"""
You are an agricultural post-harvest expert in India. Recommend the most suitable physical storage facility for:
Crop: {crop_name}
Variety: {variety}
Quantity: {quantity_kg:g} kg

Return only valid JSON with this exact shape:
{{
  "storage_type": "specific facility type",
  "search_queries": ["2 or 3 concise Google Maps search queries"],
  "reason": "one short practical reason"
}}
Use facility terms that a local Google Maps search can find, such as cold storage, pre-cooling facility, grain warehouse, silo, ripening chamber, or agricultural warehouse.
"""
    try:
        ai_text = None
        if storage_gemini_client:
            response = storage_gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    max_output_tokens=256,
                    thinking_config=types.ThinkingConfig(thinking_level="low")
                )
            )
            ai_text = response.text
        elif SECONDARY_AI_KEY:
            ai_text = secondary_ai_response([prompt], json_mode=True, max_tokens=256)
        recommendation = json.loads(ai_text or "{}")
        storage_type = str(recommendation.get("storage_type", "")).strip()
        queries = recommendation.get("search_queries")
        reason = str(recommendation.get("reason", "")).strip()
        if not storage_type or not isinstance(queries, list) or not queries:
            raise ValueError("Incomplete storage recommendation")
        return jsonify({
            "success": True,
            "source": "gemini" if gemini_client else "secondary_ai",
            "storage_type": storage_type,
            "search_queries": [str(query).strip() for query in queries[:3] if str(query).strip()],
            "reason": reason or fallback["reason"],
        })
    except Exception as error:
        app.logger.warning("Storage recommendation failed: %s", error)
        return jsonify({"success": True, "source": "rule_based", **fallback})

@app.route("/api/storage/rpc-search", methods=["GET"])
@require_auth
def rpc_search_storage_facilities():
    latitude = safe_float(request.args.get("latitude"), None)
    longitude = safe_float(request.args.get("longitude"), None)
    if latitude is None or longitude is None:
        return jsonify({"success": False, "error": "latitude and longitude are required."}), 400
    if not supabase:
        return jsonify({"success": False, "error": "Supabase is not configured on the server."}), 503
    try:
        result = supabase.rpc("find_nearest_facilities", {
            "user_lat": latitude,
            "user_lng": longitude,
            "max_distance_meters": STORAGE_SEARCH_RADIUS_METERS,
        }).execute()
        return jsonify({
            "success": True,
            "facilities": result.data or [],
            "radius_km": STORAGE_SEARCH_RADIUS_METERS // 1000,
            "source": "supabase_rpc",
        })
    except Exception as error:
        app.logger.warning("Supabase facility RPC failed: %s", error)
        return jsonify({"success": False, "error": "Storage facilities are not configured yet. Apply the Supabase schema first."}), 502

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
        crop_status = str(data.get("crop_status", "harvested")).strip().lower()
        if crop_status not in {"harvested", "growing"}:
            return jsonify({"success": False, "error": "Choose harvested or growing crop registration."}), 400
        variety = str(data.get("variety", "Desi / Local")).strip()
        field_name = str(data.get("field_name", "Field 1")).strip()
        raw_quantity = safe_float(data.get("quantity", 100), 100)
        unit = data.get("unit", "kg")
        quantity_kg = unit_to_kg(raw_quantity, unit)
        harvest_date = data.get("harvest_date") or datetime.today().strftime("%Y-%m-%d")
        planting_date = data.get("planting_date") or None
        storage_type = data.get("storage_type", "Ventilated Godown")
        image_base64 = data.get("image_base64")
        costs = data.get("production_costs", {})
        production_cost = sum(safe_float(v) for v in costs.values())

        quality_grade = "Growing" if crop_status == "growing" else "A"
        spoilage_risk = "Not applicable" if crop_status == "growing" else "Low"
        shelf_life_days = 14
        defects = "Clean surface; uniform maturity."
        recommendation = "Continue regular field monitoring and follow crop-specific care."
        processing_idea = "Standard wholesale grading and sorting."
        suggested_harvest_date = harvest_date if crop_status == "harvested" else None
        next_crop_recommendation = fallback_next_crop_plan(crop_name) if crop_status == "harvested" else []

        if gemini_client or SECONDARY_AI_KEY:
            prompt = f"""
Analyze this {crop_status} crop using the image if provided:
- Crop: {crop_name}, Variety: {variety}, Field: {field_name}
- Quantity: {quantity_kg} kg, Planting Date: {planting_date or 'not provided'}, Harvest Date: {harvest_date}
- Storage: {storage_type}

Respond strictly in valid JSON:
{{
    "quality_grade": "Growing" if the crop is growing, otherwise "A" or "B" or "C",
    "defect_summary": "Concise physical/visual defect summary",
    "spoilage_risk": "Not applicable" if the crop is growing, otherwise "Low" or "Medium" or "High",
    "shelf_life_days": integer_days_remaining,
    "recommendation": "Storage instructions",
    "processing_idea": "Value-addition/processing idea",
    "suggested_harvest_date": "YYYY-MM-DD",
    "next_crop_recommendation": [
        {{"crop": "Crop Name", "reason": "Short agronomic reason", "roi_potential": "High/Medium", "water_need": "Low/Medium/High"}}
    ]
}}
For a growing crop, suggest a harvest date based on the crop, variety, planting date, and visible maturity. For a harvested crop, use the supplied harvest date.
"""
            contents = [prompt]
            img = decode_image(image_base64)
            if img:
                contents.append(img)
            ai_text = None
            try:
                if gemini_client:
                    response = gemini_client.models.generate_content(
                        model=GEMINI_MODEL,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            max_output_tokens=256,
                            thinking_config=types.ThinkingConfig(thinking_level="low")
                        )
                    )
                    ai_text = response.text
            except Exception as e:
                print(f"Gemini quality error: {e}")
                try:
                    ai_text = secondary_ai_response(contents, json_mode=True, max_tokens=256)
                except Exception as fallback_error:
                    print(f"Secondary quality AI error: {fallback_error}")
            try:
                if ai_text:
                    ai_res = json.loads(ai_text)
                    quality_grade = ai_res.get("quality_grade", quality_grade)
                    defects = ai_res.get("defect_summary", defects)
                    spoilage_risk = ai_res.get("spoilage_risk", spoilage_risk)
                    shelf_life_days = int(ai_res.get("shelf_life_days", shelf_life_days))
                    recommendation = ai_res.get("recommendation", recommendation)
                    processing_idea = ai_res.get("processing_idea", processing_idea)
                    if crop_status == "harvested" and isinstance(ai_res.get("next_crop_recommendation"), list) and ai_res.get("next_crop_recommendation"):
                        next_crop_recommendation = ai_res["next_crop_recommendation"][:3]
                    if crop_status == "growing":
                        suggested_harvest_date = ai_res.get("suggested_harvest_date") or suggested_harvest_date
            except (TypeError, ValueError, json.JSONDecodeError) as e:
                print(f"AI quality response parsing error: {e}")

        new_batch = {
            "id": str(uuid.uuid4()),
            "farmer_id": user["id"],
            "farmer_phone": user["email"],
            "crop_name": crop_name,
            "crop_status": crop_status,
            "variety": variety,
            "field_name": field_name,
            "quantity_kg": quantity_kg,
            "input_unit": unit,
            "harvest_date": harvest_date,
            "planting_date": planting_date,
            "suggested_harvest_date": suggested_harvest_date,
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
            "next_crop_recommendation": next_crop_recommendation
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
        if gemini_client or SECONDARY_AI_KEY:
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
                try:
                    fallback_text = secondary_ai_response([prompt], json_mode=True, max_tokens=256)
                    if fallback_text:
                        next_crop_plans = json.loads(fallback_text)
                except Exception as fallback_error:
                    print(f"Secondary rotation AI error: {fallback_error}")

        if not isinstance(next_crop_plans, list) or not next_crop_plans:
            next_crop_plans = fallback_next_crop_plan(batch.get("crop_name", "Produce"))

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

def fetch_open_mandi_records(commodity="", state="", district=""):
    """Fetch fresh records from the keyless mandi service."""
    states = [state] if state else list(MANDI_SUPPORTED_STATES)
    records = []
    seen = set()

    for selected_state in states:
        params = {}
        if selected_state:
            params["state"] = selected_state
        if commodity:
            params["commodity"] = commodity

        response = requests.get(f"{MANDI_API_URL}/prices", params=params, timeout=20.0)
        response.raise_for_status()
        payload = response.json()
        provider_records = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(provider_records, list):
            continue

        for item in provider_records:
            item_district = str(item.get("district", ""))
            if district and district.lower() not in item_district.lower():
                continue
            arrival_date = item.get("arrival_date") or date.today().strftime("%Y-%m-%d")
            signature = (
                item.get("state"), item_district, item.get("market"),
                item.get("commodity"), item.get("variety"), arrival_date
            )
            if signature in seen:
                continue
            seen.add(signature)
            records.append({
                "state": item.get("state", ""),
                "district": item_district,
                "market": item.get("market", ""),
                "commodity": item.get("commodity", ""),
                "variety": item.get("variety", "General"),
                "grade": item.get("grade", ""),
                "min_price": safe_float(item.get("min_price", 0)),
                "max_price": safe_float(item.get("max_price", 0)),
                "modal_price": safe_float(item.get("modal_price", 0)),
                "arrival_date": arrival_date,
                "is_today": arrival_date == date.today().strftime("%Y-%m-%d"),
                "price_type": "Live Mandi API"
            })
    return records

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
    source = "unavailable"

    try:
        records = fetch_open_mandi_records(commodity, state, district)
        if records:
            source = "live_mandi_api"
    except (requests.RequestException, ValueError, TypeError) as error:
        app.logger.warning("Keyless mandi API fetch failed: %s", error)

    if not records and DATAGOV_KEY:
        try:
            params = {"api-key": DATAGOV_KEY, "format": "json", "limit": DATAGOV_MAX_RESULTS}
            if state:
                params["filters[state]"] = state
            if commodity:
                params["filters[commodity]"] = commodity

            resp = requests.get(
                f"https://api.data.gov.in/resource/{DATAGOV_RESOURCE_ID}",
                params=params,
                timeout=4.0
            )
            if resp.status_code != 200:
                app.logger.warning("Data.gov mandi API returned HTTP %s", resp.status_code)
                gov_records = []
            else:
                payload = resp.json()
                gov_records = payload.get("records", [])
                if not isinstance(gov_records, list):
                    app.logger.warning("Data.gov mandi API returned an invalid records field")
                    gov_records = []

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

    if not records and SECONDARY_MANDI_API_URL:
        try:
            params = {"format": "json", "limit": DATAGOV_MAX_RESULTS}
            if commodity:
                params["commodity"] = commodity
            if state:
                params["state"] = state
            if district:
                params["district"] = district

            resp = requests.get(SECONDARY_MANDI_API_URL, params=params, timeout=8.0)
            resp.raise_for_status()
            payload = resp.json()
            secondary_records = payload.get("records", payload.get("data", payload.get("results", [])))
            if isinstance(secondary_records, list):
                for r in secondary_records:
                    arr_date = r.get("arrival_date") or r.get("arrivalDate") or today_str
                    records.append({
                        "state": r.get("state") or r.get("state_name", ""),
                        "district": r.get("district") or r.get("district_name", ""),
                        "market": r.get("market") or r.get("market_name", ""),
                        "commodity": r.get("commodity") or r.get("commodity_name", ""),
                        "variety": r.get("variety") or r.get("variety_name", "General"),
                        "min_price": safe_float(r.get("min_price", r.get("minPrice", 0))),
                        "max_price": safe_float(r.get("max_price", r.get("maxPrice", 0))),
                        "modal_price": safe_float(r.get("modal_price", r.get("modalPrice", 0))),
                        "arrival_date": arr_date,
                        "is_today": (arr_date == today_str),
                        "price_type": "Secondary Government Mandi Data"
                    })
                if records:
                    source = "secondary_gov"
        except (requests.RequestException, ValueError, TypeError) as e:
            print(f"Secondary mandi API fetch error: {e}")

    response_data = {
        "success": bool(records),
        "source": source,
        "source_label": (
            "Live keyless Mandi API records" if source == "live_mandi_api"
            else "Live Data.gov.in APMC records" if source == "live_datagov"
            else "Secondary government mandi API records" if source == "secondary_gov"
            else "Live government mandi data is currently unavailable"
        ),
        "total_records": len(records),
        "records": records
    }
    if records:
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

        relevant_terms = (
            "farm", "farmer", "crop", "crops", "plant", "soil", "seed", "sowing", "harvest", "yield", "weather",
            "rain", "irrigation", "water", "fertilizer", "pesticide", "disease", "storage", "spoilage", "mandi",
            "market price", "profit", "cost", "sale", "selling", "tomato", "wheat", "potato", "onion", "खेत",
            "किसान", "फसल", "पौधा", "मिट्टी", "बीज", "बुवाई", "कटाई", "पैदावार", "मौसम", "बारिश", "सिंचाई",
            "खाद", "कीटनाशक", "बीमारी", "भंडारण", "मंडी", "भाव", "मुनाफा", "लागत", "बिक्री"
        )
        if not user_message and not image_base64:
            return jsonify({"reply": "Please ask a farming, crop, weather, mandi, or farm-finance question.", "updated_batches": user_batches(current_user()["id"])})
        if not image_base64 and not any(term in user_message.lower() for term in relevant_terms):
            reply = "मैं केवल खेती, फसल, मौसम, मंडी, भंडारण और कृषि लागत/मुनाफे से जुड़े सवालों में मदद कर सकता हूँ।" if lang == "hi" else "I can help only with farming, crops, weather, mandi prices, storage, and farm costs or profits."
            return jsonify({"reply": reply, "updated_batches": user_batches(current_user()["id"])})

        if not gemini_client and not SECONDARY_AI_KEY:
            return jsonify({
                "error": "No AI provider is configured on the server.",
                "updated_batches": user_batches(current_user()["id"])
            }), 503

        batches_context = json.dumps(user_batches(current_user()["id"]), indent=2, ensure_ascii=False)
        target_lang = "Hindi (हिंदी)" if lang == "hi" else "English"

        system_instruction = f"""
You are KrishiSahayak, an agronomist and financial advisor for Indian farmers.
Always respond strictly in: {target_lang}.
Only answer questions directly related to farming, crops, soil, weather, irrigation, crop health, storage, mandi markets, farm costs, sales, profit, or crop planning. For anything unrelated, politely say that you only support those topics and do not answer the unrelated request.

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
            if gemini_client:
                response = gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        max_output_tokens=1536,
                        thinking_config=types.ThinkingConfig(thinking_level="low")
                    )
                )
                reply_text = response.text
            else:
                reply_text = None
        except Exception as e:
            app.logger.warning("Gemini assistant request failed; trying secondary AI: %s", e)
            reply_text = None

        if not reply_text and SECONDARY_AI_KEY:
            try:
                reply_text = secondary_ai_response(contents, max_tokens=1536)
            except Exception as e:
                app.logger.exception("Secondary assistant request failed")

        if not reply_text:
            return jsonify({
                "error": "Both AI providers failed to return a response.",
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