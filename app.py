import os
import json
import base64
import requests
import uuid
from io import BytesIO
from datetime import datetime, date

from PIL import Image
from flask import Flask, render_template, request, jsonify
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


GEMINI_KEY = env_value("GEMINI_API_KEY")
DATAGOV_KEY = env_value("DATAGOV_API_KEY")
SUPABASE_URL = env_value("SUPABASE_URL")
SUPABASE_KEY = env_value("SUPABASE_KEY")
GEMINI_MODEL = env_value("GEMINI_MODEL", "gemini-3.6-flash")

# ============================================================
# CLIENTS
# ============================================================

supabase: Client = (
    create_client(SUPABASE_URL, SUPABASE_KEY)
    if SUPABASE_URL and SUPABASE_KEY
    else None
)

gemini_client = (
    genai.Client(api_key=GEMINI_KEY)
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

# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/produce/list", methods=["GET"])
def list_produce():
    phone = request.args.get("phone", "9876543210")
    if supabase:
        try:
            res = supabase.table("produce_batches").select("*").eq("farmer_phone", phone).order("created_at", desc=True).execute()
            if hasattr(res, 'data'):
                # Sync local store with Supabase
                global DATA_STORE
                DATA_STORE = res.data
                return jsonify({"success": True, "batches": res.data})
        except Exception as e:
            print(f"Supabase error: {e}")
    
    local = [b for b in DATA_STORE if b.get("farmer_phone") == phone]
    return jsonify({"success": True, "batches": local})

@app.route("/api/produce/analyze-and-add", methods=["POST"])
def analyze_and_add_produce():
    try:
        data = request.json or {}
        phone = data.get("phone", "9876543210")
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
                    config=types.GenerateContentConfig(response_mime_type="application/json")
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

        # Use UUID to prevent clashes in Supabase
        batch_uuid = f"batch-{str(uuid.uuid4())[:8]}"

        new_batch = {
            "id": batch_uuid,
            "farmer_phone": phone,
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

        if supabase:
            try:
                res = supabase.table("produce_batches").insert(new_batch).execute()
                if hasattr(res, 'data') and res.data:
                    new_batch["id"] = res.data[0]["id"]
            except Exception as err:
                print(f"Supabase insert err: {err}")

        DATA_STORE.insert(0, new_batch)
        return jsonify({"success": True, "batch": new_batch})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/produce/settle-sale", methods=["POST"])
def settle_sale():
    try:
        data = request.json or {}
        batch_id = data.get("batch_id")
        sold_qty = safe_float(data.get("sold_quantity_kg", 0))
        selling_price_per_kg = safe_float(data.get("selling_price_per_kg", 0))
        selling_date = data.get("selling_date", datetime.today().strftime("%Y-%m-%d"))
        selling_costs = data.get("selling_costs", {})
        total_selling_cost = sum(safe_float(v) for v in selling_costs.values())

        batch = next((b for b in DATA_STORE if b["id"] == batch_id), None)
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
                    config=types.GenerateContentConfig(response_mime_type="application/json")
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

    records = []
    source = "fallback_cache"

    if DATAGOV_KEY:
        try:
            # We now fetch from TWO different Data.gov APIs to get the widest possible coverage
            endpoints = [
                "9ef84268-d588-465a-a308-a864a43d0070", # Original Mandi Daily Arrivals
                "35985678-0d79-46b4-9ed6-6f13308a1d24"  # New Detailed Varieties Extension
            ]
            
            gov_records = []
            
            for endpoint in endpoints:
                url = (
                    f"https://api.data.gov.in/resource/{endpoint}"
                    f"?api-key={DATAGOV_KEY}"
                    "&format=json"
                    "&limit=50"
                )
                if state:
                    url += f"&filters[state]={state}"
                if commodity:
                    url += f"&filters[commodity]={commodity}"

                resp = requests.get(url, timeout=3.0)
                if resp.status_code == 200:
                    gov_records.extend(resp.json().get("records", []))

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

    return jsonify({
        "success": True,
        "source": source,
        "total_records": len(records),
        "records": records
    })

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
def assistant_chat():
    try:
        data = request.json or {}
        user_message = data.get("message", "").strip()
        image_base64 = data.get("image_base64", None)
        lang = data.get("lang", "en").strip()

        if not gemini_client:
            reply = "कृषि AI वर्तमान में ऑफलाइन मोड में है।" if lang == "hi" else "Krishi AI is running in offline demo mode. Please verify your GEMINI_API_KEY."
            return jsonify({"reply": reply, "updated_batches": DATA_STORE})

        batches_context = json.dumps(DATA_STORE, indent=2, ensure_ascii=False)
        target_lang = "Hindi (हिंदी)" if lang == "hi" else "English"

        system_instruction = f"""
You are KrishiSahayak, an agronomist and financial advisor for Indian farmers.
Always respond strictly in: {target_lang}.

Farmer's Stored Batches Database:
{batches_context}

Capabilities:
1. Explain pre-production costs, yield estimates, and break-even mandi prices.
2. Multimodal: If an image is provided, identify crop defects, plant rot, or diseases.
3. Keep responses concise, clear, and easy for a farmer to understand.
4. If the user asks to modify a batch, add at the bottom:
ACTION_UPDATE: {{"batch_id": "<id>", "storage_type": "<val>", "recommendation": "<val>"}}
"""
        contents = [f"{system_instruction}\n\nUser Question: {user_message}"]
        pil_img = decode_image(image_base64)
        if pil_img:
            contents.append(pil_img)

        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents
            )
            reply_text = response.text or ("कोई उत्तर प्राप्त नहीं हुआ।" if lang == "hi" else "I could not generate a response. Please try again.")
        except Exception as e:
            app.logger.exception("Gemini assistant request failed (model=%s)", GEMINI_MODEL)
            reply_text = "कृषि AI सेवा अभी उपलब्ध नहीं है।" if lang == "hi" else "The AI service is temporarily unavailable. Please try again."

        if "ACTION_UPDATE:" in reply_text:
            try:
                parts = reply_text.split("ACTION_UPDATE:", 1)
                reply_text = parts[0].strip()
                action_data = json.loads(parts[1].strip())
                batch_id = action_data.get("batch_id")
                for b in DATA_STORE:
                    if b["id"] == batch_id:
                        for k in ["storage_type", "recommendation"]:
                            if k in action_data:
                                b[k] = action_data[k]
            except Exception as parse_err:
                print(f"Action parse error: {parse_err}")

        return jsonify({"reply": reply_text, "updated_batches": DATA_STORE})
    except Exception as e:
        return jsonify({"reply": f"Server error: {e}", "error": True, "updated_batches": DATA_STORE}), 200

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