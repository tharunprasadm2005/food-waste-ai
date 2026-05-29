from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import joblib
from catboost import CatBoostRegressor, Pool
import numpy as np
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import json
import datetime
import os
from werkzeug.utils import secure_filename
import cv2
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sqlite3
from dotenv import load_dotenv
load_dotenv()


app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

from flask import session

app.secret_key = os.getenv("SECRET_KEY")
# ---------------- ADMIN CREDENTIALS ----------------
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

df = pd.read_csv("dataset/food_wastage_data.csv")
food_waste = df.groupby("Type of Food")["Wastage Food Amount"].mean()

food_labels = list(food_waste.index)
food_values = list(food_waste.values)


def get_season_food_waste():
    df = pd.read_csv("dataset/food_wastage_data.csv")

    grouped = (
        df.groupby(["Seasonality", "Type of Food"])["Wastage Food Amount"]
        .mean()
        .reset_index()
    )

    season_data = {}

    for _, row in grouped.iterrows():
        season = row["Seasonality"]
        food = row["Type of Food"]
        waste = round(row["Wastage Food Amount"], 2)

        if season not in season_data:
            season_data[season] = {}

        season_data[season][food] = waste

    return season_data


# Example storage (in real app use DB)
donations = []

# Twilio Credentials
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH")
TWILIO_PHONE = os.getenv("TWILIO_PHONE")
client = Client(TWILIO_SID, TWILIO_AUTH)


def normalize_whatsapp_number(number):
    number = number.replace("whatsapp:", "").strip()

    if number.startswith("+"):
        return "whatsapp:" + number

    return "whatsapp:+91" + number


# Store pending donations temporarily
pending_donations = {}  # key: ngo_whatsapp_number, value: donation info


# Add this right after your imports, e.g., after `from twilio.rest import Client`
def send_whatsapp(to_number, body):
    try:
        if not to_number.startswith("whatsapp:"):
            to_number = "whatsapp:" + to_number

        message = client.messages.create(from_=TWILIO_PHONE, to=to_number, body=body)

        print("✅ WhatsApp SENT:", message.sid)

    except Exception as e:
        print("❌ TWILIO ERROR:", e)


import sqlite3

conn = sqlite3.connect("donations.db")
c = conn.cursor()

try:
    c.execute("ALTER TABLE donations ADD COLUMN pickup_status TEXT DEFAULT 'Pending'")
except:
    pass

try:
    c.execute("ALTER TABLE donations ADD COLUMN volunteer_name TEXT")
except:
    pass

try:
    c.execute("ALTER TABLE donations ADD COLUMN volunteer_phone TEXT")
except:
    pass

conn.commit()
conn.close()

import sqlite3


def init_db():
    conn = sqlite3.connect("donations.db")
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food TEXT,
            quantity INTEGER,
            district TEXT,
            donor_name TEXT,
            contact TEXT,
            quality TEXT DEFAULT 'Not Provided',
            status TEXT DEFAULT 'Pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS past_donations (
            id INTEGER,
            food TEXT,
            quantity INTEGER,
            district TEXT,
            donor_name TEXT,
            contact TEXT,
            status TEXT,
            timestamp DATETIME,
            archived_time DATETIME
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS volunteers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            district TEXT,
            phone TEXT UNIQUE,
            vehicle TEXT,
            status TEXT DEFAULT 'Online',
            active_pickups INTEGER DEFAULT 0
        )
    """
    )

    c.execute(
        """
    CREATE TABLE IF NOT EXISTS past_deliveries (
        id INTEGER,
        food TEXT,
        quantity INTEGER,
        district TEXT,
        donor_name TEXT,
        contact TEXT,
        volunteer_name TEXT,
        volunteer_phone TEXT,
        timestamp DATETIME,
        completed_time DATETIME
    )
    """
    )
    conn.commit()
    conn.close()

init_db()

# ---------------- SMART PACKAGING ADVICE ----------------


def get_packaging_advice(food_type, quantity, urgency_level):
    """
    Returns realistic packaging guidance based on food type, quantity, and urgency.
    """
    food = food_type.lower()
    packaging = {}

    # ---------------- BASE PACKAGING SUGGESTIONS ----------------
    if food in ["meat", "dairy"]:
        packaging["type"] = "Airtight, food-grade containers with sealed lids"
        packaging["temperature"] = (
            "Refrigerate below 5°C; transport in ice-cooled boxes"
        )
        packaging["extra"] = "Separate raw & cooked items; avoid cross-contamination"
        packaging["safety"] = "High risk – ensure hygiene and quick transfer"

    elif food in ["fruits", "vegetables"]:
        packaging["type"] = "Ventilated crates or biodegradable boxes"
        packaging["temperature"] = "Keep cool & dry, avoid direct sunlight"
        packaging["extra"] = (
            "Do not stack heavily; maintain airflow to prevent spoilage"
        )
        packaging["safety"] = "Medium risk – handle gently to avoid bruising"

    elif food in ["baked goods", "bread", "cakes"]:
        packaging["type"] = "Cardboard or food-safe plastic boxes"
        packaging["temperature"] = "Room temperature; avoid moisture"
        packaging["extra"] = "Separate layers with parchment paper; prevent crushing"
        packaging["safety"] = "Low risk – protect shape & texture"

    elif food in ["cooked meals", "ready-to-eat"]:
        packaging["type"] = "Insulated thermal containers or compartmentalized trays"
        packaging["temperature"] = (
            "Keep hot above 60°C or cool below 5°C depending on meal type"
        )
        packaging["extra"] = (
            "Label allergens; avoid mixing foods with different storage needs"
        )
        packaging["safety"] = "Medium to high risk – temperature sensitive"

    else:
        packaging["type"] = "Standard food containers"
        packaging["temperature"] = "Store as recommended for the specific food type"
        packaging["extra"] = "Ensure containers are clean and sealed"
        packaging["safety"] = "General safety guidelines apply"

    # ---------------- BULK QUANTITY RULE ----------------
    if quantity > 100:  # realistic threshold for large catering
        packaging["bulk_advice"] = (
            "Use stackable, insulated containers; secure with straps or liners to prevent shifting"
        )

    # ---------------- URGENCY RULE ----------------
    if urgency_level in ["Critical", "Urgent"]:
        packaging["priority"] = (
            "Label containers as PRIORITY – Immediate Pickup; maintain temperature control"
        )

    # ---------------- OPTIONAL: Eco-friendly suggestions ----------------
    if food in ["fruits", "vegetables", "baked goods"]:
        packaging["eco_tip"] = (
            "Prefer biodegradable or reusable packaging where possible"
        )

    return packaging


def get_donor_dashboard(donor_name):

    conn = sqlite3.connect("donations.db")
    c = conn.cursor()

    # ---------------- TOTAL DONATIONS ----------------
    c.execute(
        """
        SELECT COUNT(*) FROM donations WHERE donor_name = ?
        UNION ALL
        SELECT COUNT(*) FROM past_donations WHERE donor_name = ?
    """,
        (donor_name, donor_name),
    )

    rows = c.fetchall()
    total_donations = sum([r[0] for r in rows])

    # ---------------- MEALS SERVED ----------------
    c.execute(
        """
        SELECT COALESCE(SUM(quantity),0) FROM donations
        WHERE donor_name = ? AND LOWER(status)='accepted'
        UNION ALL
        SELECT COALESCE(SUM(quantity),0) FROM past_donations
        WHERE donor_name = ? AND LOWER(status)='accepted'
    """,
        (donor_name, donor_name),
    )

    rows = c.fetchall()
    meals_served = sum([r[0] for r in rows])

    # ---------------- TRUST SCORE SYSTEM (NEW) ----------------

    # Total accepted donations
    c.execute(
        """
        SELECT COUNT(*) FROM donations
        WHERE donor_name = ? AND LOWER(status) = 'accepted'
        UNION ALL
        SELECT COUNT(*) FROM past_donations
        WHERE donor_name = ? AND LOWER(status) = 'accepted'
    """,
        (donor_name, donor_name),
    )

    rows = c.fetchall()
    accepted = sum([r[0] for r in rows])

    # Avoid division by zero
    if total_donations == 0:
        trust_score = 0
    else:
        trust_score = min(100, round((accepted / total_donations) * 100, 2))

    print("DEBUG Trust Score =", trust_score)

    # ---------------- POINT SYSTEM ----------------
    points = meals_served * 2

    # ---------------- LEVEL RULES ----------------
    BRONZE_LIMIT = 0
    SILVER_LIMIT = 5000
    GOLD_LIMIT = 10000
    PLATINUM_LIMIT = 30000
    DIAMOND_LIMIT = 70000
    LEGENDARY_LIMIT = 100000

    # ---------------- LEVEL DETECTION ----------------
    if meals_served >= LEGENDARY_LIMIT:
        level = "Legendary"
        next_level = "Max Level"
        next_target = LEGENDARY_LIMIT
        remaining = 0
        progress = 100

    elif meals_served >= DIAMOND_LIMIT:
        level = "Diamond"
        next_level = "Legendary"
        next_target = LEGENDARY_LIMIT
        remaining = LEGENDARY_LIMIT - meals_served
        progress = round(
            (meals_served - DIAMOND_LIMIT) / (LEGENDARY_LIMIT - DIAMOND_LIMIT) * 100, 2
        )

    elif meals_served >= PLATINUM_LIMIT:
        level = "Platinum"
        next_level = "Diamond"
        next_target = DIAMOND_LIMIT
        remaining = DIAMOND_LIMIT - meals_served
        progress = round(
            (meals_served - PLATINUM_LIMIT) / (DIAMOND_LIMIT - PLATINUM_LIMIT) * 100, 2
        )

    elif meals_served >= GOLD_LIMIT:
        level = "Gold"
        next_level = "Platinum"
        next_target = PLATINUM_LIMIT
        remaining = PLATINUM_LIMIT - meals_served
        progress = round(
            (meals_served - GOLD_LIMIT) / (PLATINUM_LIMIT - GOLD_LIMIT) * 100, 2
        )

    elif meals_served >= SILVER_LIMIT:
        level = "Silver"
        next_level = "Gold"
        next_target = GOLD_LIMIT
        remaining = GOLD_LIMIT - meals_served
        progress = round(
            (meals_served - SILVER_LIMIT) / (GOLD_LIMIT - SILVER_LIMIT) * 100, 2
        )

    else:
        level = "Bronze"
        next_level = "Silver"
        next_target = SILVER_LIMIT
        remaining = SILVER_LIMIT - meals_served
        progress = round(meals_served / SILVER_LIMIT * 100, 2)

    # ---------------- MOTIVATION MESSAGE ----------------
    if level == "Legendary":
        message = "🌟 You are a Legendary Donor! Thank you for your phenomenal support!"
    elif level == "Diamond":
        message = "💎 You are a Diamond Donor! Your generosity is outstanding!"
    elif level == "Platinum":
        message = (
            "🌟 You are a Platinum Donor! Thank you for your extraordinary support!"
        )
    elif level == "Gold":
        message = "🏆 You are a Top Donor! Thank you for your amazing support!"
    elif level == "Silver":
        message = f"🚀 Donate {remaining} more meals to reach {next_level}!"
    else:  # Bronze
        message = f"💪 Keep going! Donate {remaining} more meals to reach {next_level}!"

    conn.close()

    return {
        "total_donations": total_donations,
        "meals_served": meals_served,
        "points": points,
        "level": level,
        "trust_score": trust_score,
        # NEW FIELDS
        "next_level": next_level,
        "remaining": remaining,
        "progress": progress,
        "message": message,
    }


def get_top_donors(limit=10):
    conn = sqlite3.connect("donations.db")
    c = conn.cursor()

    c.execute(
        """
        SELECT donor_name, SUM(quantity) as total_meals
        FROM (
            SELECT donor_name, quantity FROM donations WHERE LOWER(status)='accepted'
            UNION ALL
            SELECT donor_name, quantity FROM past_donations WHERE LOWER(status)='accepted'
        )
        GROUP BY donor_name
        ORDER BY total_meals DESC
        LIMIT ?
    """,
        (limit,),
    )

    rows = c.fetchall()
    conn.close()

    top_donors = []

    for r in rows:
        top_donors.append({"name": r[0], "meals": r[1]})

    return top_donors


def get_donations():
    conn = sqlite3.connect("donations.db")
    c = conn.cursor()
    c.execute("SELECT * FROM donations")

    c.execute(
        "SELECT id, donor_name, food, quantity, district, status, timestamp, contact FROM donations"
    )
    rows = c.fetchall()
    conn.close()

    donations = []
    for r in rows:
        # ---------------- SAFE FOOD TYPE ----------------
        food_type = r[2].strip() if r[2] and r[2].strip() != "" else "unknown"
        food_type_lower = food_type.lower()

        # ---------------- SAFE QUANTITY ----------------
        try:
            quantity = int(r[3]) if r[3] is not None else 0
        except ValueError:
            quantity = 0

        # ---------------- MEALS ESTIMATION ----------------
        meals = calculate_meals(food_type, quantity)

        # ---------------- URGENCY CALCULATION ----------------
        if food_type_lower in ["meat", "dairy"]:
            risk_factor = 1.5
        else:
            risk_factor = 1.0

        urgency_score = quantity * risk_factor

        if urgency_score > 200:
            urgency = "Critical"
            eta = "1–2 Hours"
        elif urgency_score > 100:
            urgency = "Urgent"
            eta = "2–4 Hours"
        elif urgency_score > 50:
            urgency = "Moderate"
            eta = "4–6 Hours"
        else:
            urgency = "Normal"
            eta = "6–10 Hours"

        # ---------------- EXPIRY CALCULATION ----------------
        try:
            donation_time = datetime.datetime.strptime(r[6], "%Y-%m-%d %H:%M:%S")
            expiry_time = donation_time + datetime.timedelta(hours=24)
            expiry_date = expiry_time.strftime("%Y-%m-%d %H:%M")
        except:
            expiry_date = "—"

        donations.append(
            {
                "id": r[0],
                "donor_name": r[1] if r[1] else "Anonymous",
                "food_type": food_type,
                "quantity": quantity,
                "meals": meals,
                "district": r[4] if r[4] else "Unknown",
                "status": r[5] if r[5] else "Pending",
                "timestamp": r[6] if r[6] else "",
                "expiry_date": expiry_date,
                "contact": r[7] if r[7] else "",
                "is_urgent": urgency in ["Critical", "Urgent"],
                "urgency": urgency,
                "eta": eta,
                "latitude": district_coords.get(r[4], (0, 0))[0],
                "longitude": district_coords.get(r[4], (0, 0))[1],
            }
        )

    return donations


def archive_donations():
    conn = sqlite3.connect("donations.db")
    c = conn.cursor()

    # Move ACCEPTED donations
    c.execute(
        """
        INSERT INTO past_donations
        SELECT id, food, quantity, district, donor_name, contact,
               status, timestamp, datetime('now'),
               volunteer_name, volunteer_phone
        FROM donations
        WHERE status='Accepted'
    """
    )

    c.execute("DELETE FROM donations WHERE status='Accepted'")

    # Move donations older than 24 hours
    c.execute(
        """
        INSERT INTO past_donations
        SELECT id, food, quantity, district, donor_name, contact,
               status, timestamp, datetime('now'),
               volunteer_name, volunteer_phone
        FROM donations
        WHERE timestamp <= datetime('now','-24 hours')
    """
    )

    c.execute(
        """
        DELETE FROM donations
        WHERE timestamp <= datetime('now','-24 hours')
    """
    )

    conn.commit()
    conn.close()


def get_dashboard_analytics():

    conn = sqlite3.connect("donations.db")

    df_active = pd.read_sql_query("SELECT * FROM donations", conn)
    df_past = pd.read_sql_query("SELECT * FROM past_donations", conn)

    conn.close()

    # Ensure empty/all-NA columns are removed before concatenation
    df_active = df_active.dropna(axis=1, how='all')
    df_past = df_past.dropna(axis=1, how='all')

    # Then concatenate
    df = pd.concat([df_active, df_past], ignore_index=True)

    if df.empty:
        return {}

    # Convert timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # ================= BASIC SUMMARY =================

    total_donations = len(df)
    total_food = int(df["quantity"].sum())

    accepted = df[df["status"].str.lower() == "accepted"]
    successful = len(accepted)

    pending = len(df[df["status"].str.lower() == "pending"])

    success_rate = (
        round((successful / total_donations) * 100, 2) if total_donations else 0
    )
    delay_percent = (
        round((pending / total_donations) * 100, 2) if total_donations else 0
    )

    # ================= TIME ANALYSIS (Realistic Synthetic Timestamps) =================
    np.random.seed(42)  # reproducibility
    num_rows = len(df)

    # 1️⃣ Weighted hours (simulate lunch/dinner peaks)
    hours = np.arange(24)
    hour_weights = np.array([1] * 24)  # default weight
    # Lunch: 11-14, Dinner: 18-21
    hour_weights[11:15] = 5
    hour_weights[18:22] = 5
    hour_probs = hour_weights / hour_weights.sum()

    # 2️⃣ Weighted months (simulate festive months: higher wastage in Oct & Dec)
    months = np.arange(1, 13)
    month_weights = np.ones(12)
    month_weights[[9, 11]] = 3  # October & December
    month_probs = month_weights / month_weights.sum()

    # 3️⃣ Generate random dates for 2025
    dates = []
    for _ in range(num_rows):
        month = np.random.choice(months, p=month_probs)
        day = np.random.randint(
            1, 29
        )  # Simplify: max 28 days to avoid month-end issues
        hour = np.random.choice(hours, p=hour_probs)
        minute = np.random.randint(0, 60)
        second = np.random.randint(0, 60)
        dates.append(
            pd.Timestamp(
                year=2025, month=month, day=day, hour=hour, minute=minute, second=second
            )
        )

    df["timestamp"] = pd.to_datetime(dates)

    # 4️⃣ Extract hour and month
    df["hour"] = df["timestamp"].dt.hour
    df["month"] = df["timestamp"].dt.month

    # 5️⃣ Compute distributions
    hourly_distribution = df.groupby("hour").size().sort_index().to_dict()
    monthly_distribution = df.groupby("month").size().sort_index().to_dict()

    # ================= TOP DONORS =================

    top_donors = (
        accepted.groupby("donor_name")["quantity"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
        .to_dict()
    )

    # ================= FOOD STATS =================

    food_stats = (
        df.groupby("food")["quantity"].sum().sort_values(ascending=False).head(5)
    )

    food_stats = {k: int(v) for k, v in food_stats.items()}

    # ================= RESPONSE TIME (Realistic Simulation) =================

    # Filter pending donations
    df_pending = df[df["status"].str.lower() == "pending"].copy()

    if not df_pending.empty:
        np.random.seed(42)
        # Assign random delays in hours
        # 80% of pending: 1-48 hours, 20%: 72-168 hours
        n = len(df_pending)
        short_delays = np.random.randint(1, 49, size=int(n * 0.8))
        long_delays = np.random.randint(72, 169, size=n - len(short_delays))
        all_delays = np.concatenate([short_delays, long_delays])
        np.random.shuffle(all_delays)

        # Generate realistic timestamps for pending donations
        df_pending["timestamp"] = pd.Timestamp.now() - pd.to_timedelta(
            all_delays, unit="h"
        )

        # Compute average response in hours
        avg_response = round(
            (pd.Timestamp.now() - df_pending["timestamp"]).dt.total_seconds().mean()
            / 3600,
            2,
        )
    else:
        avg_response = 0

    # ================= ENVIRONMENTAL IMPACT =================

    total_kg = df["quantity"].sum()

    co2_saved = round(total_kg * 2.5, 2)  # kg CO2 saved
    water_saved = round(total_kg * 1500, 2)  # liters water saved

    # ================= FORECAST =================

    recent_data = df.tail(14)  # last 2 weeks data

    daily_avg = recent_data["quantity"].mean()

    forecast_next_week = round(daily_avg * 7, 2)

    # ================= RECEIVER PERFORMANCE =================

    accepted = accepted[accepted["district"].notna()]
    accepted = accepted[accepted["district"] != ""]

    top_receivers = (
        accepted.groupby("district")["quantity"]
        .sum()
        .sort_values(ascending=False)
        .head(5)
    )

    top_receivers = {k: int(v) for k, v in top_receivers.items()}

    # ================= SYSTEM HEALTH =================

    system_status = {
        "Database": "Online",
        "ML Models": "Active",
        "WhatsApp": "Connected",
        "Server": "Running",
    }

    # ================= SMART INSIGHTS =================

    insights = []

    # Donation success performance
    if success_rate >= 90:
        insights.append(
            "Excellent donation success rate. Food redistribution system is highly efficient."
        )
    elif success_rate >= 75:
        insights.append(
            "Good success rate, but there is room to improve food recovery efficiency."
        )
    else:
        insights.append(
            "Low donation success rate detected. Improve coordination with NGOs and donors."
        )

    # Pending donation management
    if pending > 20:
        insights.append(
            "Critical number of pending donations. Increase pickup vehicles or NGO partners."
        )
    elif pending > 10:
        insights.append(
            "Moderate pending donations. Improve logistics scheduling to reduce delays."
        )

    # NGO response efficiency
    if avg_response > 8:
        insights.append(
            "Very slow NGO response time. Consider expanding partner network."
        )
    elif avg_response > 5:
        insights.append(
            "Response time slightly high. Improve notification and coordination systems."
        )

    # Waste prediction insights
    if forecast_next_week > 100:
        insights.append(
            "Very high food waste predicted next week. Immediate redistribution planning required."
        )
    elif forecast_next_week > 70:
        insights.append(
            "High food waste forecast. Increase food donation awareness and NGO capacity."
        )
    elif forecast_next_week < 30:
        insights.append(
            "Low waste expected next week. Current food planning appears effective."
        )

    # Final system stability message
    if not insights:
        insights.append(
            "System operating normally with balanced food supply and donation demand."
        )

    # ================= ALERTS =================

    alerts = []

    if pending > 5:
        alerts.append("⚠ High Pending Requests")

    if success_rate < 60:
        alerts.append("⚠ Low Pickup Success Rate")

    if avg_response > 6:
        alerts.append("⚠ Slow Response Time")

    if not alerts:
        alerts.append("✅ System Operating Normally")

    # ================= ML METRICS =================

    ml_metrics = {
        "rf_mae": rf_metrics["MAE"],
        "rf_rmse": rf_metrics["RMSE"],
        "rf_r2": rf_metrics["R2"],
        "cb_mae": cb_metrics["MAE"],
        "cb_rmse": cb_metrics["RMSE"],
        "cb_r2": cb_metrics["R2"],
        "xg_mae": xgb_metrics["MAE"],
        "xg_rmse": xgb_metrics["RMSE"],
        "xg_r2": xgb_metrics["R2"],
        "lgb_mae": lgb_metrics["MAE"],
        "lgb_rmse": lgb_metrics["RMSE"],
        "lgb_r2": lgb_metrics["R2"],
    }

    # ================= FINAL RETURN =================

    return {
        # Summary
        "total_donations": total_donations,
        "total_food": total_food,
        "successful": successful,
        "pending": pending,
        "success_rate": success_rate,
        "delay_percent": delay_percent,
        # Time Analysis
        "hourly": hourly_distribution,  # from synthetic timestamp analysis
        "monthly": monthly_distribution,  # from synthetic timestamp analysis
        # Rankings
        "top_donors": top_donors,
        "top_receivers": top_receivers,
        # Food
        "food_stats": food_stats,
        # Performance
        "avg_response": avg_response,
        # Environment
        "co2_saved": co2_saved,
        "water_saved": water_saved,
        # Forecast
        "forecast": forecast_next_week,
        # Health
        "system_status": system_status,
        # AI
        "insights": insights,
        "alerts": alerts,
        "ml_metrics": ml_metrics,
    }


# ---------------- LOAD MODELS & FILES ----------------
rf = joblib.load("model/random_forest.pkl")

cb = CatBoostRegressor()
cb.load_model("model/catboost_model.cbm")

xg = joblib.load("model/xgboost.pkl")
lgbm = joblib.load("model/lightgbm.pkl")

encoders = joblib.load("model/encoders.pkl")

rf_metrics = joblib.load("model/rf_metrics.pkl")
cb_metrics = joblib.load("model/cb_metrics.pkl")
xgb_metrics = joblib.load("model/xg_metrics.pkl")
lgb_metrics = joblib.load("model/lgb_metrics.pkl")

donations = []

# ---------------- STATIC ANALYSIS DATA ----------------
high_waste_food = {
    "Meat": "High",
    "Dairy": "Medium",
    "Vegetables": "Medium",
    "Fruits": "Low",
    "Baked Goods": "Low",
}
food_event_waste = {
    "Marriage": {
        "Meat": 0.45,
        "Dairy": 0.25,
        "Vegetables": 0.15,
        "Fruits": 0.10,
        "Baked Goods": 0.05,
    },
    "Festival": {
        "Meat": 0.40,
        "Dairy": 0.30,
        "Vegetables": 0.15,
        "Fruits": 0.10,
        "Baked Goods": 0.05,
    },
    "Birthday": {
        "Meat": 0.30,
        "Dairy": 0.25,
        "Vegetables": 0.20,
        "Fruits": 0.15,
        "Baked Goods": 0.10,
    },
}

tamilnadu_districts = [
    "Ariyalur",
    "Chengalpattu",
    "Chennai",
    "Coimbatore",
    "Cuddalore",
    "Dharmapuri",
    "Dindigul",
    "Erode",
    "Kallakurichi",
    "Kanchipuram",
    "Karur",
    "Krishnagiri",
    "Madurai",
    "Mayiladuthurai",
    "Nagapattinam",
    "Namakkal",
    "Nilgiris",
    "Perambalur",
    "Pudukkottai",
    "Ramanathapuram",
    "Ranipet",
    "Salem",
    "Sivaganga",
    "Tenkasi",
    "Thanjavur",
    "Theni",
    "Thoothukudi",
    "Tiruchirappalli",
    "Tirunelveli",
    "Tirupattur",
    "Tiruppur",
    "Tiruvallur",
    "Tiruvannamalai",
    "Tiruvarur",
    "Vellore",
    "Viluppuram",
    "Virudhunagar",
]

ngos_by_district = {
    "Ariyalur": [
        {
            "name": "Adaikalamadha Home",
            "address": "Elakurichi, Ariyalur",
            "contact": "9488622150",
        },
        {
            "name": "St. Raphael’s Integrated Complex",
            "address": "Andimadam, Ariyalur",
            "contact": "9600243444",
        },
    ],
    "Chengalpattu": [
        {
            "name": "Duraisamy Generous Social Education Association",
            "address": "Madhurandhagam, Chengalpattu",
            "contact": "7010766210",
        }
    ],
    "Chennai": [
        {
            "name": "Chennai Food Bank",
            "address": "Anna Nagar, Chennai",
            "contact": "9444444444",
        }
    ],
    "Coimbatore": [
        {
            "name": "Universal Peace Foundation Old Age Home",
            "address": "Annur, Coimbatore",
            "contact": "8015914401",
        }
    ],
    "Cuddalore": [
        {
            "name": "Cuddalore Care NGO",
            "address": "Cuddalore Town",
            "contact": "9876541230",
        }
    ],
    "Dharmapuri": [
        {
            "name": "Dharmapuri Social Welfare",
            "address": "Dharmapuri Town",
            "contact": "9876512340",
        }
    ],
    "Dindigul": [
        {
            "name": "Dindigul Food Support",
            "address": "Dindigul Main Road",
            "contact": "9786877690",
        }
    ],
    "Erode": [
        {
            "name": "Erode Helping Hands",
            "address": "Perundurai Road",
            "contact": "9786543210",
        }
    ],
    "Kallakurichi": [
        {
            "name": "Kallakurichi Aid Society",
            "address": "Kallakurichi Town",
            "contact": "9876501234",
        }
    ],
    "Kanchipuram": [
        {
            "name": "Kanchipuram Food Bank",
            "address": "Kanchipuram Town",
            "contact": "9876544321",
        }
    ],
    "Karur": [
        {
            "name": "Karur Helping Hands",
            "address": "Karur Town",
            "contact": "9876545678",
        }
    ],
    "Krishnagiri": [
        {
            "name": "Krishnagiri Social Welfare",
            "address": "Krishnagiri Town",
            "contact": "9876548765",
        }
    ],
    "Madurai": [
        {
            "name": "Madurai Food Relief",
            "address": "Madurai Town",
            "contact": "9876598765",
        }
    ],
    "Mayiladuthurai": [
        {
            "name": "Mayiladuthurai Care NGO",
            "address": "Mayiladuthurai Town",
            "contact": "9876549087",
        }
    ],
    "Nagapattinam": [
        {
            "name": "Nagapattinam Helping Hands",
            "address": "Nagapattinam Town",
            "contact": "9876543212",
        }
    ],
    "Namakkal": [
        {
            "name": "Namakkal Food Support",
            "address": "Namakkal Town",
            "contact": "2549611748",
        }
    ],
    "Nilgiris": [
        {
            "name": "Nilgiris Social Welfare",
            "address": "Ooty, Nilgiris",
            "contact": "9876543412",
        }
    ],
    "Perambalur": [
        {
            "name": "Perambalur Aid Society",
            "address": "Perambalur Town",
            "contact": "9876543534",
        }
    ],
    "Pudukkottai": [
        {
            "name": "Pudukkottai Helping Hands",
            "address": "Pudukkottai Town",
            "contact": "9876543678",
        }
    ],
    "Ramanathapuram": [
        {
            "name": "Ramanathapuram Food Aid",
            "address": "Ramanathapuram Town",
            "contact": "9876543890",
        }
    ],
    "Ranipet": [
        {
            "name": "Ranipet Social Support",
            "address": "Ranipet Town",
            "contact": "9876543999",
        }
    ],
    "Salem": [
        {
            "name": "Local Food Relief NGO",
            "address": "Salem Town",
            "contact": "9876543210",
        }
    ],
    "Sivaganga": [
        {
            "name": "Sivaganga Aid NGO",
            "address": "Sivaganga Town",
            "contact": "9876543001",
        }
    ],
    "Tenkasi": [
        {
            "name": "Tenkasi Food Support",
            "address": "Tenkasi Town",
            "contact": "9876543002",
        }
    ],
    "Thanjavur": [
        {
            "name": "Thanjavur Social Welfare",
            "address": "Thanjavur Town",
            "contact": "9876543003",
        }
    ],
    "Theni": [
        {
            "name": "Theni Helping Hands",
            "address": "Theni Town",
            "contact": "9876543004",
        }
    ],
    "Thoothukudi": [
        {
            "name": "Thoothukudi Food Aid",
            "address": "Thoothukudi Town",
            "contact": "9876543005",
        }
    ],
    "Tiruchirappalli": [
        {
            "name": "Trichy Food Support",
            "address": "Tiruchirappalli Town",
            "contact": "9876543006",
        }
    ],
    "Tirunelveli": [
        {
            "name": "Tirunelveli Social Welfare",
            "address": "Tirunelveli Town",
            "contact": "9876543007",
        }
    ],
    "Tirupattur": [
        {
            "name": "Tirupattur Aid NGO",
            "address": "Tirupattur Town",
            "contact": "9876543008",
        }
    ],
    "Tiruppur": [
        {
            "name": "Tiruppur Helping Hands",
            "address": "Tiruppur Town",
            "contact": "9876543009",
        }
    ],
    "Tiruvallur": [
        {
            "name": "Tiruvallur Food Bank",
            "address": "Tiruvallur Town",
            "contact": "9876543010",
        }
    ],
    "Tiruvannamalai": [
        {
            "name": "Tiruvannamalai Social Support",
            "address": "Tiruvannamalai Town",
            "contact": "9876543011",
        }
    ],
    "Tiruvarur": [
        {
            "name": "Tiruvarur Aid NGO",
            "address": "Tiruvarur Town",
            "contact": "9876543012",
        }
    ],
    "Vellore": [
        {
            "name": "Vellore Food Relief",
            "address": "Vellore Town",
            "contact": "9876543013",
        }
    ],
    "Viluppuram": [
        {
            "name": "Viluppuram Helping Hands",
            "address": "Viluppuram Town",
            "contact": "9876543014",
        }
    ],
    "Virudhunagar": [
        {
            "name": "Jeevakkal Social Welfare Youth Society",
            "address": "Sivakasi West",
            "contact": "9994467883",
        }
    ],
}

nearby_districts = {
    "Ariyalur": ["Perambalur", "Tiruchirappalli", "Cuddalore"],
    "Chengalpattu": ["Kanchipuram", "Viluppuram", "Chennai"],
    "Chennai": ["Thiruvallur", "Kanchipuram", "Chengalpattu"],
    "Coimbatore": ["Tiruppur", "Erode", "Nilgiris"],
    "Cuddalore": ["Villupuram", "Ariyalur", "Perambalur"],
    "Dharmapuri": ["Krishnagiri", "Salem", "Tiruvannamalai"],
    "Dindigul": ["Karur", "Tiruchirappalli", "Madurai", "Pudukkottai"],
    "Erode": ["Coimbatore", "Tiruppur", "Salem"],
    "Kallakurichi": ["Villupuram", "Cuddalore", "Salem"],
    "Kanchipuram": ["Chengalpattu", "Thiruvallur", "Chennai"],
    "Karur": ["Tiruchirappalli", "Dindigul", "Namakkal"],
    "Krishnagiri": ["Dharmapuri", "Vellore", "Tirupattur"],
    "Madurai": ["Dindigul", "Theni", "Tirunelveli"],
    "Mayiladuthurai": ["Nagapattinam", "Tiruvarur", "Thanjavur"],
    "Nagapattinam": ["Tiruvarur", "Thanjavur", "Mayiladuthurai"],
    "Namakkal": ["Salem", "Karur", "Erode"],
    "Nilgiris": ["Coimbatore", "Erode", "Tiruppur"],
    "Perambalur": ["Ariyalur", "Tiruchirappalli", "Cuddalore"],
    "Pudukkottai": ["Dindigul", "Thanjavur", "Tiruchirappalli"],
    "Ramanathapuram": ["Sivaganga", "Thoothukudi", "Tirunelveli"],
    "Ranipet": ["Vellore", "Tiruvannamalai", "Kanchipuram"],
    "Salem": ["Erode", "Namakkal", "Dharmapuri"],
    "Sivaganga": ["Ramanathapuram", "Madurai", "Thoothukudi"],
    "Tenkasi": ["Tirunelveli", "Thoothukudi", "Virudhunagar"],
    "Thanjavur": ["Tiruvarur", "Nagapattinam", "Pudukkottai"],
    "Theni": ["Madurai", "Dindigul", "Tirunelveli"],
    "Thoothukudi": ["Tirunelveli", "Virudhunagar", "Sivaganga"],
    "Tiruchirappalli": ["Karur", "Perambalur", "Dindigul"],
    "Tirunelveli": ["Thoothukudi", "Tenkasi", "Madurai"],
    "Tirupattur": ["Krishnagiri", "Vellore", "Dharmapuri"],
    "Tiruppur": ["Coimbatore", "Erode", "Nilgiris"],
    "Tiruvallur": ["Chennai", "Kanchipuram", "Thiruvannamalai"],
    "Tiruvannamalai": ["Vellore", "Dharmapuri", "Tiruvallur"],
    "Tiruvarur": ["Nagapattinam", "Thanjavur", "Mayiladuthurai"],
    "Vellore": ["Tiruvannamalai", "Ranipet", "Krishnagiri"],
    "Viluppuram": ["Cuddalore", "Kanchipuram", "Chengalpattu"],
    "Virudhunagar": ["Sivaganga", "Tenkasi", "Thoothukudi"],
}

# Sample coordinates for districts
district_coords = {
    "Ariyalur": (11.1401, 79.0786),
    "Chengalpattu": (12.6876, 79.9858),
    "Chennai": (13.0827, 80.2707),
    "Coimbatore": (11.0168, 76.9558),
    "Cuddalore": (11.7490, 79.7643),
    "Dharmapuri": (12.1365, 78.1572),
    "Dindigul": (10.3620, 77.9801),
    "Erode": (11.3380, 77.7290),
    "Kallakurichi": (11.7395, 78.9588),
    "Kancheepuram": (12.8342, 79.7036),
    "Kanniyakumari": (8.1788, 77.4288),
    "Karur": (10.9601, 78.0760),
    "Krishnagiri": (12.5195, 78.2138),
    "Madurai": (9.9252, 78.1198),
    "Mayiladuthurai": (11.1035, 79.6532),
    "Nagapattinam": (10.7667, 79.8458),
    "Namakkal": (11.2180, 78.1672),
    "Nilgiris": (11.4064, 76.6932),  # Udagamandalam (Ooty)
    "Perambalur": (11.2186, 78.8718),
    "Pudukkottai": (10.3800, 78.8203),
    "Ramanathapuram": (9.3720, 78.8318),
    "Ranipet": (12.9332, 79.3142),
    "Salem": (11.6643, 78.1460),
    "Sivaganga": (9.8469, 78.4788),
    "Tenkasi": (8.9588, 77.3150),
    "Thanjavur": (10.7870, 79.1378),
    "Theni": (10.0000, 77.4833),
    "Thiruvarur": (10.7715, 79.6329),
    "Thiruvallur": (13.1439, 79.9099),
    "Thiruvannamalai": (12.2261, 79.0747),
    "Thoothukudi": (8.7642, 78.1348),  # Tuticorin
    "Tiruchirappalli": (10.7905, 78.7047),
    "Tirunelveli": (8.7139, 77.7563),
    "Tirupathur": (12.4950, 78.5678),
    "Tiruppur": (11.1085, 77.3411),
    "Viluppuram": (11.9459, 79.4889),
    "Vellore": (12.9165, 79.1325),
    "Virudhunagar": (9.5833, 77.9670),
}

# ---------------- VOLUNTEER SYSTEM (NEW) ----------------


def calculate_distance_km(d1, d2):

    lat1, lon1 = district_coords.get(d1, (0, 0))
    lat2, lon2 = district_coords.get(d2, (0, 0))

    distance = ((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2) ** 0.5 * 111

    return round(distance, 2)


def estimate_eta(distance, vehicle):

    speed = {"Bike": 35, "Car": 40, "Van": 30}

    avg_speed = speed.get(vehicle, 35)

    eta = (distance / avg_speed) * 60

    return int(eta + 10)


def match_volunteers(district, volunteers_list):
    available = []

    for v in volunteers_list:  # use the passed list
        # Skip busy volunteers
        if v["status"] == "Busy":
            continue

        if v["availability"] != "Online":
            continue
        if v["active_tasks"] >= v["capacity"]:
            continue

        distance = calculate_distance_km(district, v["district"])
        if distance > 250:
            continue

        eta = estimate_eta(distance, v["vehicle"])
        score = distance * 0.4 + eta * 0.3 + v["active_tasks"] * 2 - v["rating"] * 1.5

        available.append(
            {
                "name": v["name"],
                "contact": v["phone"],
                "vehicle": v["vehicle"] if v["vehicle"] else "None",
                "distance": distance,
                "eta": eta,
                "rating": v["rating"] if v["rating"] else "N/A",
                "score": round(score, 2),
                "district": v["district"],
            }
        )

    return sorted(available, key=lambda x: x["score"])[:3]


def chatbot_response(user_message, donor_name=None):
    """
    Full-featured chatbot response function for donors.
    Handles 17 intents, including donation status, AI-driven priority, packaging advice, and community updates.
    """
    msg = user_message.lower().strip()

    # ---------------- DONOR DASHBOARD ----------------
    dashboard = get_donor_dashboard(donor_name)

    if not dashboard:
        return "❌ No donation record found."

    total_meals = dashboard.get("meals_served", 0)
    reward_points = dashboard.get("points", 0)
    donor_level = dashboard.get("level", "N/A")
    trust_score = dashboard.get("trust_score", 0)
    total_donations = dashboard.get("total_donations", 0)
    # ADD THESE
    next_level = dashboard.get("next_level", "N/A")
    remaining = dashboard.get("remaining", 0)
    progress = dashboard.get("progress", 0)

    # ---------------- GET LATEST DONATION ----------------
    conn = sqlite3.connect("donations.db")
    c = conn.cursor()

    c.execute(
        """
        SELECT district, status, quality, quantity, timestamp, food
        FROM donations
        WHERE donor_name = ?
        ORDER BY id DESC LIMIT 1
        """,
        (donor_name,),
    )
    row = c.fetchone()
    conn.close()

    if row:
        district, status, quality, quantity, donation_time_str, food_type = row
        quantity = quantity or 0
        urgency_score = round(quantity * 1.0, 2)  # Example urgency score
        # Parse timestamp safely
        try:
            donation_time = datetime.datetime.strptime(
                donation_time_str, "%Y-%m-%d %H:%M:%S"
            )
            expiry_time = donation_time + datetime.timedelta(hours=24)
        except Exception as e:
            donation_time = expiry_time = None
    else:
        district = status = quality = food_type = "N/A"
        quantity = urgency_score = 0
        donation_time = expiry_time = None

    # ---------------- INTENTS ----------------

    if any(word in msg for word in ["where", "pending", "accepted"]):
        return f"📦 Your latest donation in {district} is currently '{status}'."

    elif any(word in msg for word in ["donor level", "badge"]):
        return f"🏅 Your donor level is {donor_level}."

    elif any(word in msg for word in ["points", "rewards", "point"]):
        return f"⭐ You have {reward_points} reward points."

    elif any(word in msg for word in ["trust", "score"]):
        return f"🤝 Your trust score is {trust_score}%."

    elif any(word in msg for word in ["meals", "served"]):
        return f"🍽️ You have served {total_meals} meals."

    elif any(word in msg for word in ["history", "total donations"]):
        return f"📜 You have made {total_donations} total donations."

    elif any(word in msg for word in ["quality"]):
        return f"🧠 Food quality status: {quality}"

    elif any(word in msg for word in ["urgency"]):
        return f"⚡ Urgency score of latest donation: {urgency_score}"

    elif any(word in msg for word in ["pickup", "eta"]):
        if urgency_score > 100:
            eta = "1–2 Hours"
        elif urgency_score > 50:
            eta = "2–4 Hours"
        elif urgency_score > 25:
            eta = "4–6 Hours"
        else:
            eta = "6–10 Hours"
        return f"🚚 Estimated pickup time: {eta}"

    elif any(word in msg for word in ["who will pick", "which ngo"]):
        return f"🏢 NGOs from {district} district are prioritized for pickup."

    elif any(word in msg for word in ["impact", "environment"]):
        priority_level = "High" if urgency_score > 100 else "Normal"
        co2_saved = round(quantity * 2.5, 2)
        water_saved = round(quantity * 1500, 2)
        return (
            f"🌱 AI-Driven Priority: Your donation is considered '{priority_level}' for redistribution.\n"
            f"🌍 Environmental Impact: Estimated CO₂ saved: {co2_saved} kg, Water saved: {water_saved} liters."
        )

    elif any(word in msg for word in ["delivery"]):
        district_ngos = ngos_by_district.get(district, [])
        ngo_names = (
            ", ".join([ngo["name"] for ngo in district_ngos])
            if district_ngos
            else "No NGOs available"
        )
        return f"🚚 You can choose NGO pickup ({ngo_names}) or schedule your own delivery for this donation."

    elif any(
        word in msg
        for word in ["packaging", "temperature", "handling", "safety", "bulk"]
    ):
        advice = get_packaging_advice(food_type, quantity, urgency_score)
        response = (
            f"📦 Packaging Type: {advice.get('type', 'N/A')}\n"
            f"🌡️ Temperature Control: {advice.get('temperature', 'N/A')}\n"
            f"🤝 Handling Instructions: {advice.get('extra', 'N/A')}\n"
            f"🛡️ Safety Level: {advice.get('safety', 'N/A')}\n"
        )
        if advice.get("bulk_advice"):
            response += f"📦 Bulk Handling: {advice.get('bulk_advice')}\n"
        if advice.get("priority"):
            response += f"⚡ Priority Advice: {advice.get('priority')}\n"
        return response

    elif any(
        word in msg
        for word in ["nearby ngo", "nearby organization", "nearest ngo", "ngo list"]
    ):
        nearby = nearby_districts.get(district, [])
        prioritized_ngos = []
        for dist in [district] + nearby:
            prioritized_ngos.extend(ngos_by_district.get(dist, []))
        if prioritized_ngos:
            response = "🏢 Nearby NGOs for pickup:\n"
            for ngo in prioritized_ngos[:5]:
                response += f"- {ngo['name']} ({dist}) 📞 {ngo['contact']}\n"
            return response
        else:
            return "🏢 No NGOs nearby currently prioritized for your donation."

    elif any(word in msg for word in ["expiry", "safety alert"]):
        now = datetime.datetime.now()
        if expiry_time and expiry_time > now:
            remaining_hours = round((expiry_time - now).total_seconds() / 3600, 2)
            return f"⏰ Food will expire in ~{remaining_hours} hours. ⚡ Urgency: {urgency_score}. Please ensure timely pickup."
        else:
            return "⏰ Food is safe or already expired. No immediate alerts."

    elif any(word in msg for word in ["community", "heroes", "top donors"]):
        top_donors_list = get_top_donors(limit=5)
        if top_donors_list:
            response = "❤️ Community Heroes:\n"
            for donor in top_donors_list:
                response += f"- {donor['name']}: {donor['meals']} Meals Donated\n"
            return response
        else:
            return "❤️ No top donors yet. Be the first hero! 💚"

    elif any(word in msg for word in ["next level", "level progress", "rank"]):
        return (
            f"🏅 Current Level: {donor_level}\n"
            f"🚀 Next Level: {next_level}\n"
            f"🍽 Meals Needed: {remaining}\n"
            f"📊 Progress: {progress}%"
        )

    elif any(word in msg for word in ["remaining"]):
        return f"🍽 You need {remaining} more meals to reach {next_level} level."

    else:
        return (
            "🤖 I can help you with:\n\n"
            "• Donation status\n"
            "• Pickup ETA\n"
            "• Donor level\n"
            "• Reward points\n"
            "• Trust score\n"
            "• Meals served\n"
            "• Food quality\n"
            "• Urgency score\n"
            "• Donation history\n"
            "• NGO assignment\n"
            "• AI-driven priority & environmental impact\n"
            "• Delivery options\n"
            "• Smart packaging advice\n"
            "• Nearby NGOs\n"
            "• Food expiry & safety alerts\n"
            "• Community heroes / top donors"
        )


# ---------------- MARKET PRICE PER KG (₹) ----------------

FOOD_PRICES = {
    "Meat": 320,
    "Dairy": 180,
    "Fruits": 90,
    "Vegetables": 70,
    "Baked Goods": 150,
    "Grains": 60,
    "Rice": 55,
    "Other": 100,
}
# ---------------- CO2 EMISSION FACTOR (kg CO2 / kg food) ----------------

CO2_FACTORS = {
    "Meat": 6.0,
    "Dairy": 3.2,
    "Rice": 4.0,
    "Fruits": 1.1,
    "Vegetables": 0.9,
    "Baked Goods": 2.1,
    "Grains": 1.4,
    "Other": 2.0,
}
# ---------------- FOOD PORTION SIZE (KG PER PERSON) ----------------
PORTION_SIZE = {
    "rice": 0.4,
    "biryani": 0.5,
    "meat": 0.45,
    "dairy": 0.3,
    "vegetables": 0.35,
    "fruits": 0.25,
    "baked goods": 0.2,
    "grains": 0.4,
    "other": 0.3,
}


# ---------------- KG TO MEALS CONVERTER ----------------
def calculate_meals(food_type, quantity_kg):

    food = food_type.lower().strip()

    portion = PORTION_SIZE.get(food, PORTION_SIZE["other"])

    meals = int(quantity_kg / portion)

    return max(meals, 1)  # At least 1 meal


# ---------------- ROUTES ----------------
@app.route("/")
def home():
    # Get real admin dashboard analytics
    data = get_dashboard_analytics()

    # Pass the data to the template
    return render_template("index.html", data=data)


@app.route("/predict", methods=["GET", "POST"])
def predict():
    if request.method == "POST":

        try:
            data = {
                "Type of Food": request.form["food"].strip(),
                "Number of Guests": int(request.form["guests"]),
                "Event Type": request.form["event"].strip(),
                "Quantity of Food": int(request.form["quantity"]),
                "Storage Conditions": request.form["storage"].strip(),
                "Purchase History": request.form["purchase"].strip(),
                "Seasonality": request.form["season"].strip(),
                "Preparation Method": request.form["prep"].strip(),
                "Geographical Location": request.form["location"].strip(),
                "Pricing": request.form["pricing"].strip(),
            }
        except ValueError:
            return render_template(
                "predict.html", error="Please fill all numeric fields correctly."
            )

        df = pd.DataFrame([data])

        catboost_df = df.copy()

        # Load real season vs food waste data
        season_food_waste = get_season_food_waste()

        # ---------------- ENCODING ----------------
        for col in encoders:
            if col in df.columns:
                try:
                    df[col] = encoders[col].transform(df[col])
                except ValueError:
                    df[col] = 0  # or some default encoding

        # ---------------- MODEL PREDICTIONS ----------------
        rf_pred = round(rf.predict(df)[0], 2)
        cb_pred = round(cb.predict(catboost_df)[0], 2)
        xg_pred = round(xg.predict(df)[0], 2)
        lgb_pred = round(lgbm.predict(df)[0], 2)

        final_pred = round(
            (0.15 * rf_pred)
            + (0.15 * xg_pred)
            + (0.20 * lgb_pred)
            + (0.50 * cb_pred),  # CatBoost highest weight (PROPOSED MODEL)
            2,
        )

        # ---------------- BASE METRIC (MUST COME FIRST) ----------------

        prepared_qty = float(request.form.get("quantity", 1))  # From form

        if prepared_qty <= 0:
            prepared_qty = 1  # Safety fallback

        waste_ratio = final_pred / prepared_qty

        event_type = data["Event Type"]
        season = data["Seasonality"]

        food_waste_estimation = {}
        if event_type in food_event_waste:
            for food, ratio in food_event_waste[event_type].items():
                food_waste_estimation[food] = round(final_pred * ratio, 2)
        season = data["Seasonality"]

        season_waste_estimation = {}
        if season in season_food_waste:
            for food, ratio in season_food_waste[season].items():
                season_waste_estimation[food] = round(final_pred * ratio, 2)

        # ======================================================
        # EXTRA CONCEPT 1: MODEL AGREEMENT SCORE (ADDED)
        # ======================================================
        preds = np.array([rf_pred, cb_pred, xg_pred, lgb_pred])

        mean_pred = np.mean(preds)
        std_pred = np.std(preds)

        agreement_score = round(max(0, 100 - (std_pred / mean_pred) * 100), 2)

        # ======================================================
        # EXTRA CONCEPT 2: CONFIDENCE INTERVAL (ADDED)
        # ======================================================
        prediction_std = np.std([rf_pred, cb_pred, xg_pred, lgb_pred])
        lower_bound = round(final_pred - prediction_std, 2)
        upper_bound = round(final_pred + prediction_std, 2)

        # ---------------- FEATURE IMPORTANCE ----------------

        cat_features = [
            "Type of Food",
            "Event Type",
            "Storage Conditions",
            "Purchase History",
            "Seasonality",
            "Preparation Method",
            "Geographical Location",
            "Pricing",
        ]

        pool = Pool(catboost_df, cat_features=cat_features)

        shap_values = cb.get_feature_importance(type="ShapValues", data=pool)
        shap_vals = shap_values[0][:-1]
        feature_impact = dict(zip(df.columns, shap_vals))
        top_feature = max(feature_impact, key=lambda k: abs(feature_impact[k]))

        # ---------------- FEATURE IMPORTANCE PLOT (ADD THIS) ----------------

        sorted_features = sorted(
            feature_impact.items(), key=lambda x: abs(x[1]), reverse=True
        )

        features = [x[0] for x in sorted_features]
        values = [abs(x[1]) for x in sorted_features]

        plt.figure(figsize=(8, 5))

        plt.barh(features, values, color="#4db8ee")

        plt.gca().invert_yaxis()

        # Dark theme for your UI
        plt.title("Feature Importance", color="grey")
        plt.xlabel("Impact on Prediction", color="grey")

        plt.xticks(color="grey")
        plt.yticks(color="grey")

        # Transparent background for dark UI
        plt.gca().set_facecolor("none")
        plt.gcf().patch.set_alpha(0)

        plt.tight_layout()

        plt.savefig("static/feature_importance.png", transparent=True, dpi=300)

        plt.close()

        suggestions = {
            "Quantity of Food": "Reduce over-preparation using guest history.",
            "Number of Guests": "Avoid overestimation using attendance data.",
            "Event Type": "Buffet events produce more waste — plan carefully.",
            "Storage Conditions": "Improve storage to extend food life.",
            "Seasonality": "Adjust menu based on seasonal demand.",
            "Pricing": "Dynamic pricing helps reduce leftovers.",
        }
        advice = suggestions.get(
            top_feature, "Monitor this factor to reduce food wastage."
        )

        # ======================================================
        # EXTRA CONCEPT 3: OVERPRODUCTION INDEX (ADDED)
        # ======================================================
        overproduction_index = round((final_pred / df["Quantity of Food"][0]) * 100, 2)

        # ---------------- WASTAGE SCENARIOS ----------------
        normal_pred = final_pred

        # Tomorrow
        tomorrow_df = df.copy()
        tomorrow_df["Number of Guests"] = int(df["Number of Guests"][0] * 1.15)
        tomorrow_df["Quantity of Food"] = int(df["Quantity of Food"][0] * 1.15)

        tomorrow_pred = round(
            np.mean(
                [
                    rf.predict(tomorrow_df)[0],
                    cb.predict(tomorrow_df)[0],
                    xg.predict(tomorrow_df)[0],
                    lgbm.predict(tomorrow_df)[0],
                ]
            ),
            2,
        )

        # Festival
        festival_df = df.copy()
        festival_df["Number of Guests"] = int(df["Number of Guests"][0] * 1.3)
        festival_df["Quantity of Food"] = int(df["Quantity of Food"][0] * 1.4)

        if "Seasonality" in encoders and "Festival" in encoders["Seasonality"].classes_:
            festival_df["Seasonality"] = encoders["Seasonality"].transform(["Festival"])

        festival_pred = round(
            np.mean(
                [
                    rf.predict(festival_df)[0],
                    cb.predict(festival_df)[0],
                    xg.predict(festival_df)[0],
                    lgbm.predict(festival_df)[0],
                ]
            ),
            2,
        )

        # ✅ Ensure Festival Wastage > Normal Wastage
        if festival_pred <= normal_pred:
            festival_pred = round(normal_pred * 1.25, 2)

        # ======================================================
        # EXTRA CONCEPT 4: DEMAND SURGE INDICATOR (ADDED)
        # ======================================================
        if tomorrow_pred > normal_pred:
            demand_surge = "Increasing Demand Expected"
        elif tomorrow_pred < normal_pred:
            demand_surge = "Demand Likely to Decrease"
        else:
            demand_surge = "Stable Demand"

        # ---------------- EXTRA SMART INSIGHTS (DYNAMIC) ----------------
        max_waste = 80  # Maximum wastage observed in dataset
        waste_amount = final_pred  # Predicted wastage for this input

        # Ensure we never exceed dataset max
        if waste_amount > max_waste:
            waste_amount = max_waste

        # Calculate ratio based on max possible
        waste_ratio = waste_amount / max_waste

        # Dynamic risk levels based on dataset max
        if waste_ratio > 0.6:  # >48kg
            risk_level = "⚠️ High Risk"
        elif waste_ratio > 0.35:  # 28–48kg
            risk_level = "⚡ Medium Risk"
        else:  # <=28kg
            risk_level = "✅ Low Risk"

        # Dynamic donation urgency based on risk
        if waste_ratio > 0.6:
            donation_urgency = "Immediate Donation Recommended"
        elif waste_ratio > 0.35:
            donation_urgency = "Donation Advised"
        elif waste_ratio > 0.2:
            donation_urgency = "Monitor for Possible Donation"
        else:
            donation_urgency = "No Immediate Action Needed"

        # Dynamic prep recommendation
        if waste_ratio > 0.6:
            prep_recommendation = (
                "Significant overproduction! Reduce preparation by 25–30%."
            )
        elif waste_ratio > 0.35:
            prep_recommendation = "Moderate surplus. Reduce preparation by 15–20%."
        elif waste_ratio > 0.2:
            prep_recommendation = "Minor surplus. Fine-tune planning by 5–10%."
        else:
            prep_recommendation = "Food planning is well optimized."

        # ---------------- DYNAMIC FINANCIAL LOSS ----------------
        food_type = data["Type of Food"]

        price_per_kg = FOOD_PRICES.get(food_type, FOOD_PRICES["Other"])

        cost_loss = round(final_pred * price_per_kg, 2)

        # ---------------- CATEGORY-WISE CO2 IMPACT ----------------
        co2_factor = CO2_FACTORS.get(food_type, CO2_FACTORS["Other"])

        co2_impact = round(final_pred * co2_factor, 2)

        # ======================================================
        # EXTRA CONCEPT 5: DONATION PRIORITY SCORE (ADDED)
        # ======================================================
        donation_priority = min(100, round(final_pred * 3, 2))
        donatable_food = {}

        for food, qty in food_waste_estimation.items():
            if food in ["Meat", "Dairy"] and qty > 5:
                donatable_food[food] = round(qty * 0.6, 2)  # 60% safe donation
            elif food in ["Vegetables", "Fruits"]:
                donatable_food[food] = round(qty * 0.8, 2)

        # ======================================================
        # EXTRA CONCEPT 6: WASTE REDUCTION SIMULATION (ADDED)
        # ======================================================
        reduced_df = df.copy()
        reduced_df["Quantity of Food"] = int(df["Quantity of Food"][0] * 0.85)
        reduced_pred = np.mean(
            [
                rf.predict(reduced_df)[0],
                cb.predict(reduced_df)[0],
                xg.predict(reduced_df)[0],
                lgbm.predict(reduced_df)[0],
            ]
        )

        reduced_waste = round(reduced_pred, 2)
        # ✅ Ensure optimized waste is not higher than current
        if reduced_waste >= cb_pred:
            reduced_waste = round(cb_pred * 0.85, 2)

        waste_saved = round(cb_pred - reduced_waste, 2)

        model_confidence = round(
            np.mean(
                [
                    rf_metrics["R2"],
                    cb_metrics["R2"],
                    xgb_metrics["R2"],
                    lgb_metrics["R2"],
                ]
            )
            * 100,
            2,
        )

        # Prepare season chart data
        season_labels = list(season_food_waste.keys())

        season_chart_data = {}

        for season, foods in season_food_waste.items():
            for food, value in foods.items():

                if food not in season_chart_data:
                    season_chart_data[food] = []

                season_chart_data[food].append(round(value, 2))

        return render_template(
            "result.html",
            final_pred=final_pred,
            rf_pred=rf_pred,
            cb_pred=cb_pred,
            xg_pred=xg_pred,
            lgb_pred=lgb_pred,
            top_feature=top_feature,
            advice=advice,
            prep_recommendation=prep_recommendation,
            high_waste_foods=high_waste_food,
            normal_pred=normal_pred,
            tomorrow_pred=tomorrow_pred,
            festival_pred=festival_pred,
            risk_level=risk_level,
            cost_loss=cost_loss,
            co2_impact=co2_impact,
            donation_urgency=donation_urgency,
            model_confidence=model_confidence,
            food_waste_estimation=food_waste_estimation,
            season_waste_estimation=season_waste_estimation,
            donatable_food=donatable_food,
            food_labels=food_labels,
            food_values=food_values,
            season_labels=season_labels,
            season_chart_data=season_chart_data,
            # -------- EXTRA DATA PASSED (SAFE) --------
            agreement_score=agreement_score,
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            overproduction_index=overproduction_index,
            demand_surge=demand_surge,
            donation_priority=donation_priority,
            reduced_waste=reduced_waste,
            waste_saved=waste_saved,
            rf_mae=rf_metrics["MAE"],
            rf_rmse=rf_metrics["RMSE"],
            rf_r2=rf_metrics["R2"],
            cb_mae=cb_metrics["MAE"],
            cb_rmse=cb_metrics["RMSE"],
            cb_r2=cb_metrics["R2"],
            xg_mae=xgb_metrics["MAE"],
            xg_rmse=xgb_metrics["RMSE"],
            xg_r2=xgb_metrics["R2"],
            lgb_mae=lgb_metrics["MAE"],
            lgb_rmse=lgb_metrics["RMSE"],
            lgb_r2=lgb_metrics["R2"],
        )

    return render_template("predict.html")


@app.route("/donor", methods=["GET", "POST"])
def donor():

    ngos_grouped = {}
    selected_district = None
    form_data = None
    expiry = None

    if request.method == "POST":

        # 1️⃣ Collect form data
        form_data = {
            "food": request.form.get("food"),
            "quantity": int(request.form.get("quantity")),
            "district": request.form.get("district"),
            "donor_name": request.form.get("donor_name"),
            "contact": (request.form.get("contact")),
        }
        # -------- OPTIONAL IMAGE UPLOAD --------

        quality_result = "Not Provided"

        file = request.files.get("food_image")

        if file and file.filename != "":
            try:
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)

                # 🔥 Simple AI Simulation Based on Filename
                name = filename.lower()

                if "expired" in name:
                    quality_result = "Expired"
                elif "medium" in name:
                    quality_result = "Medium"
                else:
                    quality_result = "Fresh"

            except Exception as e:
                print("Image processing failed:", e)
                quality_result = "Not Provided"

        quantity = form_data["quantity"]
        selected_district = form_data["district"]

        # 2️⃣ Add NGOs from selected district
        ngos_grouped[selected_district] = ngos_by_district.get(
            selected_district, []
        ).copy()

        # 3️⃣ Add NGOs from nearby districts
        for nearby in nearby_districts.get(selected_district, []):
            nearby_ngos = ngos_by_district.get(nearby, [])
            if nearby_ngos:
                ngos_grouped[nearby] = nearby_ngos

        # -------- NGO PRIORITY ASSIGNMENT (DISTANCE BASED) --------
        prioritized_ngos = []

        # Same district → highest priority
        for ngo in ngos_by_district.get(selected_district, []):
            prioritized_ngos.append(
                {**ngo, "priority": 1, "district": selected_district}
            )

        # Nearby districts → lower priority
        for nearby in nearby_districts.get(selected_district, []):
            for ngo in ngos_by_district.get(nearby, []):
                prioritized_ngos.append({**ngo, "priority": 2, "district": nearby})

        # Sort NGOs by priority
        prioritized_ngos = sorted(prioritized_ngos, key=lambda x: x["priority"])

        # ------------------ ALL NGOs TABLE ------------------
        all_ngos = []

        for district, ngos in ngos_by_district.items():
            for ngo in ngos:
                all_ngos.append(
                    {
                        "district": district,
                        "name": ngo["name"],
                        "address": ngo["address"],
                        "contact": ngo["contact"],
                    }
                )

        # Optional: sort by district and NGO name
        all_ngos = sorted(all_ngos, key=lambda x: (x["district"], x["name"]))

        # -------- MAP SIMULATION DATA --------
        map_data = {"donor_district": selected_district, "ngos": prioritized_ngos}

        # 4️⃣ Save donation to DB
        conn = sqlite3.connect("donations.db")
        c = conn.cursor()
        c.execute(
            """
            INSERT INTO donations (food, quantity, district, donor_name, contact, quality)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                form_data["food"],
                form_data["quantity"],
                form_data["district"],
                form_data["donor_name"],
                form_data["contact"],
                quality_result,
            ),
        )
        # -------- DONOR REPUTATION LEVEL --------

        conn.commit()
        conn.close()

        dashboard = get_donor_dashboard(form_data["donor_name"])
        level = dashboard["level"]

        # -------- PICKUP URGENCY & ETA --------
        food_type = form_data["food"].lower()
        quantity = form_data["quantity"]

        # Food risk factor
        if food_type in ["meat", "dairy"]:
            risk_factor = 1.5
        else:
            risk_factor = 1.0

        urgency_score = round(quantity * risk_factor, 2)

        if urgency_score > 100:
            pickup_eta = "1–2 Hours"
        elif urgency_score > 50:
            pickup_eta = "2–4 Hours"
        elif urgency_score > 25:
            pickup_eta = "4–6 Hours"
        else:
            pickup_eta = "6–10 Hours"

        # 5️⃣ Notify NGOs (console simulation)

        # 6️⃣ Dashboard metrics (safe defaults – DB later)

        quantity = int(form_data["quantity"])

        # 7️⃣ Food expiry logic

        if quantity >= 100:
            expiry = {
                "status": "Critical",
                "message": "🚨 Immediate pickup required (1–2 hours)",
            }
        elif quantity > 50:
            expiry = {"status": "Urgent", "message": "⚠ Pickup within 4–6 hours"}
        else:
            expiry = {"status": "Fresh", "message": "✔ Safe for donation"}

        top_donors = get_top_donors()

        # Smart Pickup Time (basic AI logic - demo)
        from datetime import datetime

        current_hour = datetime.now().hour

        if 6 <= current_hour < 11:
            pickup_time = "Today 12:30 PM (Low Traffic)"
        elif 11 <= current_hour < 16:
            pickup_time = "Today 6:30 PM (Low Traffic)"
        elif 16 <= current_hour < 20:
            pickup_time = "Tomorrow 8:00 AM (Best Slot)"
        else:
            pickup_time = "Tomorrow 10:00 AM (Low Traffic)"

        # ---------------- SMART PACKAGING ADVICE ----------------
        packaging_advice = get_packaging_advice(
            form_data["food"], form_data["quantity"], expiry["status"]
        )

        # 8️⃣ Render donor page
        return render_template(
            "donor.html",
            ngos_grouped=ngos_grouped,
            tamilnadu_districts=tamilnadu_districts,
            selected_district=selected_district,
            data=form_data,
            dashboard=dashboard,
            expiry=expiry,
            prioritized_ngos=prioritized_ngos,
            all_ngos=all_ngos,
            pickup_eta=pickup_eta,
            urgency_score=urgency_score,
            map_data=map_data,
            level=level,
            top_donors=top_donors,
            pickup_time=pickup_time,
            packaging_advice=packaging_advice,
            quality=quality_result,
        )
    donor_name = request.args.get("donor_name", "")

    dashboard = (
        get_donor_dashboard(donor_name)
        if donor_name
        else {"total_donations": 0, "meals_served": 0, "points": 0, "level": "Bronze"}
    )
    # GET request
    return render_template(
        "donor.html",
        dashboard=dashboard,
        level="Bronze",
        expiry={"status": "—", "message": "—"},
        pickup_eta="—",
        urgency_score="—",
        ngos_grouped={},
        selected_district=None,
        map_data={"donor_district": ""},
        top_donors=get_top_donors(),
    )


# ------------------ NEW /donate ROUTE ------------------
@app.route("/donate", methods=["POST"])
def donate():
    donation = {
        "ngo_name": request.form["ngo_name"],
        "ngo_contact": request.form["ngo_contact"],
        "donor_name": request.form["donor_name"],
        "donor_contact": request.form["donor_contact"],
        "food": request.form["food"],
        "quantity": request.form["quantity"],
    }

    # Save donation to DB (or temporary list)
    conn = sqlite3.connect("donations.db")
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO donations (food, quantity, district, donor_name, contact)
        VALUES (?, ?, ?, ?, ?)
    """,
        (
            donation["food"],
            donation["quantity"],
            request.form.get(
                "district", ""
            ),  # optional: you can send district in hidden input
            donation["donor_name"],
            donation["donor_contact"],
        ),
    )
    conn.commit()
    conn.close()

    # Redirect back to donor page (or show confirmation)
    return redirect(url_for("donor"))


@app.route("/notify", methods=["POST"])
def notify():
    ngo_name = request.form.get("ngo_name")
    ngo_contact = request.form.get("ngo_contact")  # RAW number
    donor_name = request.form.get("donor_name")
    donor_contact = request.form.get("donor_contact")
    food = request.form.get("food")
    quantity = request.form.get("quantity")
    location = request.form.get("location")
    print("DEBUG LOCATION:", location)

    formatted_ngo_number = normalize_whatsapp_number(ngo_contact)
    formatted_donor_number = normalize_whatsapp_number(donor_contact)

    pending_donations.setdefault(formatted_ngo_number, []).append(
        {
            "donor_name": donor_name,
            "donor_contact": formatted_donor_number,
            "food": food,
            "quantity": quantity,
            "ngo_name": ngo_name,
            "ngo_contact": formatted_ngo_number,
        }
    )

    message_body = f"""
    🚨 *URGENT FOOD RESCUE ALERT*

    Hello {ngo_name} Team,

    A food donation is ready for pickup. Please arrange collection as soon as possible.

    📦 *Food Details*
    • Item: {food}
    • Quantity: {quantity} kg
    • Estimated Meals: {calculate_meals(food, int(quantity))} people

    👤 *Donor Details*
    • Name: {donor_name}
    • Contact: {donor_contact}

    ⏳ *Pickup Window*
    Please collect the donation within the next *1–2 hours* to ensure freshness.

    📲 Kindly contact the donor before arrival to coordinate the pickup.

    Thank you for your prompt action in reducing food waste.
    """
    send_whatsapp(formatted_ngo_number, message_body)

    return redirect(url_for("receiver"))


@app.route("/receiver", methods=["GET", "POST"])
def receiver():
    archive_donations()
    donations = get_donations()

    import sqlite3

    # -------- ACTIVE DONATIONS --------
    active_meals = 0
    urgent_count = 0

    for d in donations:
        status = str(d["status"]).strip().lower()
        urgency = str(d["urgency"]).strip().lower()

        qty = int(d["meals"])

        if status == "accepted":
            active_meals += qty

        if urgency in ["urgent", "critical"]:
            urgent_count += 1

    # -------- ARCHIVED DONATIONS --------
    conn = sqlite3.connect("donations.db")
    c = conn.cursor()

    c.execute(
        """
        SELECT SUM(quantity)
        FROM past_donations
        WHERE LOWER(TRIM(status)) = 'accepted'
    """
    )

    row = c.fetchone()
    archived_meals = row[0] if row[0] else 0

    conn.close()

    # -------- FINAL METRICS --------
    metrics = {
        "total_donations": len(donations),
        "meals_saved": active_meals + archived_meals,
        "urgent": urgent_count,
    }

    # ---------------- VOLUNTEER SUGGESTION ENGINE ----------------

    import sqlite3

    # Fetch all volunteers once
    conn = sqlite3.connect("donations.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT * FROM volunteers
        WHERE availability='Online'
        AND status='Available'
        AND active_tasks < capacity
        """
    )

    all_volunteers = c.fetchall()
    conn.close()
    # Print for debugging
    for v in all_volunteers:
        print(dict(v))

    volunteer_suggestions = []

    for d in donations:
        district = d.get("district", "Unknown")
        urgency = d.get("urgency", "Normal")

        # get top 3 volunteers for this district
        matches = match_volunteers(district, all_volunteers)

        # Format info for template
        formatted_volunteers = []
        for v in matches:
            formatted_volunteers.append(
                {
                    "name": v["name"],
                    "phone": v["contact"],
                    "level": v["level"] if "level" in v.keys() else "Bronze",
                    "rating": v["rating"] if "rating" in v.keys() else "N/A",
                    "vehicle": v["vehicle"] if "vehicle" in v.keys() else "N/A",
                    "distance": v["distance"] if "distance" in v.keys() else "N/A",
                    "eta": v["eta"] if "eta" in v.keys() else "N/A",
                }
            )

        volunteer_suggestions.append(
            {
                "id": d["id"],
                "donor": d["donor_name"],
                "food_type": d["food_type"],
                "quantity": d["quantity"],
                "meals": d["meals"],
                "district": district,
                "urgency": urgency,
                "volunteers": formatted_volunteers,
            }
        )

    if request.method == "POST":
        conn = sqlite3.connect("donations.db")
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # -------- SINGLE ACCEPT --------
        accept_id = request.form.get("accept")
        if accept_id:
            c.execute("SELECT * FROM donations WHERE id=?", (accept_id,))
            donation = c.fetchone()
            if donation and donation["status"] == "Pending":
                c.execute(
                    "UPDATE donations SET status='Accepted' WHERE id=?", (accept_id,)
                )
                message = (
                    f"Hello {donation['donor_name']},\n\n"
                    f"Your donation ({donation['food']}) has been ACCEPTED ✅.\n"
                    "Our receiver will collect it soon.\n\n"
                    "Thank you for reducing food waste 💚"
                )
                send_whatsapp(donation["contact"], message)

        # -------- SINGLE REJECT --------
        reject_id = request.form.get("reject")
        if reject_id:
            c.execute("SELECT * FROM donations WHERE id=?", (reject_id,))
            donation = c.fetchone()
            if donation and donation["status"] == "Pending":
                c.execute(
                    "UPDATE donations SET status='Rejected' WHERE id=?", (reject_id,)
                )
                message = (
                    f"Hello {donation['donor_name']},\n\n"
                    f"Your donation ({donation['food']}) has been REJECTED ❌.\n"
                    "Thank you for your contribution 💚"
                )
                send_whatsapp(donation["contact"], message)

        # -------- BATCH ACCEPT --------
        if "batch_accept" in request.form:
            selected = request.form.getlist("selected")
            for donation_id in selected:
                c.execute("SELECT * FROM donations WHERE id=?", (donation_id,))
                donation = c.fetchone()
                if donation and donation["status"] == "Pending":
                    c.execute(
                        "UPDATE donations SET status='Accepted' WHERE id=?",
                        (donation_id,),
                    )
                    message = (
                        f"Hello {donation['donor_name']},\n\n"
                        f"Your donation ({donation['food']}) has been ACCEPTED ✅.\n"
                        "Our receiver will collect it soon.\n\n"
                        "Thank you for reducing food waste 💚"
                    )
                    send_whatsapp(donation["contact"], message)

        # -------- BATCH REJECT --------
        if "batch_reject" in request.form:
            selected = request.form.getlist("selected")
            for donation_id in selected:
                c.execute("SELECT * FROM donations WHERE id=?", (donation_id,))
                donation = c.fetchone()
                if donation and donation["status"] == "Pending":
                    c.execute(
                        "UPDATE donations SET status='Rejected' WHERE id=?",
                        (donation_id,),
                    )
                    message = (
                        f"Hello {donation['donor_name']},\n\n"
                        f"Your donation ({donation['food']}) has been REJECTED ❌.\n"
                        "Thank you for your contribution 💚"
                    )
                    send_whatsapp(donation["contact"], message)

        conn.commit()
        conn.close()
        return redirect(url_for("receiver"))

    # -------- CHART DATA --------
    from collections import defaultdict

    food_summary = defaultdict(int)
    for d in donations:
        food_summary[d["food_type"]] += d["quantity"]

    chart_labels = list(food_summary.keys())
    chart_data = list(food_summary.values())

    # -------- FILTERS --------
    districts = sorted(list(set(d["district"] for d in donations)))
    food_types = sorted(list(set(d["food_type"] for d in donations)))

    # -------- PAST DONATIONS --------
    conn = sqlite3.connect("donations.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM past_donations ORDER BY archived_time DESC")
    past_donations = c.fetchall()
    conn.close()

    return render_template(
        "receiver.html",
        donations=donations,
        past_donations=past_donations,
        metrics=metrics,
        chart_labels=chart_labels,
        chart_data=chart_data,
        districts=districts,
        food_types=food_types,
        volunteer_suggestions=volunteer_suggestions,
    )


@app.route("/hard_test")
def hard_test():
    send_whatsapp("whatsapp:+916379918385", "HARD TEST MESSAGE")
    return "sent"


@app.route("/assign_volunteer", methods=["POST"])
def assign_volunteer():

    donation_id = request.form.get("donation_id")
    volunteer_name = request.form.get("volunteer_name")
    volunteer_phone = request.form.get("volunteer_phone")

    # ---------------- DATABASE UPDATE ----------------

    conn = sqlite3.connect("donations.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT * FROM donations WHERE id=?", (donation_id,))
    donation = c.fetchone()

    if not donation:
        conn.close()
        return redirect(url_for("receiver"))

    c.execute(
        """
        UPDATE donations
        SET pickup_status=?, volunteer_name=?, volunteer_phone=?
        WHERE id=?
    """,
        ("Assigned", volunteer_name, volunteer_phone, donation_id),
    )

    conn.commit()
    conn.close()

    # ---------------- WHATSAPP MESSAGE ----------------

    donor = donation["donor_name"]
    food = donation["food"]
    quantity = donation["quantity"]
    district = donation["district"]

    message = f"""
    🚨 Food Rescue Pickup Notification

    Hello {volunteer_name},

    A new food donation pickup has been assigned to you.

    📦 Food Item: {food}
    🍽 Quantity: {quantity}
    👤 Donor: {donor}
    📍 Location: {district}

    Please visit your dashboard to ACCEPT or DECLINE this assignment.

    Thank you for your valuable contribution in reducing food waste.
    """

    try:

        formatted_number = normalize_whatsapp_number(volunteer_phone)

        print("Sending WhatsApp to:", formatted_number)

        client.messages.create(from_=TWILIO_PHONE, to=formatted_number, body=message)

        print("✅ WhatsApp notification sent")

    except Exception as e:

        print("❌ TWILIO ERROR:", e)

    return redirect(url_for("receiver"))


# ---------------- ADMIN LOGIN ----------------


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:

            session["admin_logged_in"] = True
            session["admin_name"] = username

            return redirect(url_for("admin"))

        else:
            return render_template(
                "admin_login.html", error="Invalid Username or Password"
            )

    return render_template("admin_login.html")


@app.route("/admin")
def admin():

    # Check Login
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    data = get_dashboard_analytics()

    return render_template("admin.html", data=data, admin=session.get("admin_name"))


@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(url_for("admin_login"))


@app.route("/chatbot", methods=["POST"])
def chatbot():

    user_message = request.form.get("message")
    donor_name = request.form.get("donor_name")

    reply = chatbot_response(user_message, donor_name)

    return {"reply": reply}


@app.route("/volunteer_dashboard")
def volunteer_dashboard():

    conn = sqlite3.connect("donations.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # ---------- FETCH TASKS (existing code) ----------
    c.execute(
        """
        SELECT * FROM donations
        WHERE volunteer_phone IS NOT NULL
    """
    )
    rows = c.fetchall()

    c.execute(
        """
        SELECT * FROM past_deliveries
        WHERE volunteer_phone IS NOT NULL
    """
    )
    past_rows = c.fetchall()

    tasks = []
    active_tasks = []
    past_tasks = []

    for r in rows:

        task = dict(r)

        # ---------------- FOOD FIX ----------------
        task["food_type"] = r["food"]

        # ---------------- MEALS CALCULATION ----------------
        quantity = int(r["quantity"]) if r["quantity"] else 0
        task["meals"] = calculate_meals(r["food"], quantity)

        # ---------------- DONOR CONTACT FIX ----------------
        task["donor_contact"] = r["contact"]

        # ---------------- VOLUNTEER CONTACT FIX ----------------
        phone = r["volunteer_phone"]

        if phone and phone.startswith("whatsapp:"):
            phone = phone.replace("whatsapp:", "")

        task["volunteer_contact"] = phone

        # ---------------- REAL NGO FROM DICTIONARY ----------------
        district = r["district"]

        if district in ngos_by_district and ngos_by_district[district]:
            ngo = ngos_by_district[district][0]  # first NGO in that district
            task["ngo_name"] = ngo["name"]
            task["ngo_contact"] = ngo["contact"]
        else:
            task["ngo_name"] = "NGO Not Available"
            task["ngo_contact"] = "N/A"

        # 🔹 SPLIT TASKS
        if r["pickup_status"] in ["Assigned", "Accepted"]:
            active_tasks.append(task)

    for r in past_rows:

        task = dict(r)

        task["food_type"] = r["food"]

        quantity = int(r["quantity"]) if r["quantity"] else 0
        task["meals"] = calculate_meals(r["food"], quantity)

        task["donor_contact"] = r["contact"]

        phone = r["volunteer_phone"]

        if phone and phone.startswith("whatsapp:"):
            phone = phone.replace("whatsapp:", "")

        task["volunteer_contact"] = phone

        district = r["district"]

        if district in ngos_by_district and ngos_by_district[district]:
            ngo = ngos_by_district[district][0]
            task["ngo_name"] = ngo["name"]
            task["ngo_contact"] = ngo["contact"]
        else:
            task["ngo_name"] = "NGO Not Available"
            task["ngo_contact"] = "N/A"

        past_tasks.append(task)

    # ---------- REAL VOLUNTEER IMPACT STATS (existing code) ----------
    c.execute("SELECT COUNT(*) FROM donations WHERE pickup_status='Completed'")
    completed_pickups = c.fetchone()[0]

    c.execute("SELECT SUM(quantity) FROM donations WHERE pickup_status='Completed'")
    total_food = c.fetchone()[0] or 0

    # ---------- REAL VOLUNTEER IMPACT STATS FROM PAST DONATIONS ----------
    completed_pickups = len(past_tasks)

    total_food = sum(int(t["quantity"]) for t in past_tasks)

    meals_delivered = sum(t["meals"] for t in past_tasks)

    families_helped = len(set(t["ngo_name"] for t in past_tasks))

    # ---------------- DYNAMIC VOLUNTEER REWARDS ----------------
    c.execute("SELECT * FROM volunteers")
    all_volunteers = c.fetchall()

    volunteer_rewards = []

    for v in all_volunteers:
        # Count completed deliveries for this volunteer
        c.execute(
            """
            SELECT COUNT(*) FROM past_deliveries
            WHERE volunteer_phone=?
        """,
            (v["phone"],),
        )
        deliveries = c.fetchone()[0]

        points = deliveries * 10

        # Determine level
        if deliveries >= 100:
            level = "Platinum"
        elif deliveries >= 50:
            level = "Gold"
        elif deliveries >= 20:
            level = "Silver"
        else:
            level = "Bronze"

        volunteer_rewards.append(
            {
                "name": v["name"],
                "phone": v["phone"],
                "deliveries": deliveries,
                "points": points,
                "level": level,
            }
        )

    conn.close()

    return render_template(
        "volunteer_dashboard.html",
        active_tasks=active_tasks,
        past_tasks=past_tasks,
        completed_pickups=completed_pickups,
        total_food=total_food,
        meals_delivered=meals_delivered,
        families_helped=families_helped,
        volunteers=volunteer_rewards,  # dynamically updated from DB
    )


@app.route("/accept_pickup/<int:donation_id>")
def accept_pickup(donation_id):
    conn = sqlite3.connect("donations.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch donation
    c.execute("SELECT * FROM donations WHERE id=?", (donation_id,))
    donation = c.fetchone()

    # Fetch the assigned volunteer
    c.execute("SELECT * FROM volunteers WHERE phone=?", (donation["volunteer_phone"],))
    volunteer = c.fetchone()

    if volunteer:
        # Mark volunteer as busy
        c.execute(
            "UPDATE volunteers SET status='Busy' WHERE phone=?", (volunteer["phone"],)
        )

        # Update active tasks
        new_active = volunteer["active_tasks"] + 1
        c.execute(
            "UPDATE volunteers SET active_tasks=? WHERE phone=?",
            (new_active, volunteer["phone"]),
        )

    # Mark donation as accepted
    c.execute(
        """
        UPDATE donations
        SET pickup_status='Accepted'
        WHERE id=?
    """,
        (donation_id,),
    )
    

    conn.commit()
    conn.close()
    return redirect(request.referrer)

@app.route("/complete_pickup/<int:donation_id>")
def complete_pickup(donation_id):

    conn = sqlite3.connect("donations.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch donation
    c.execute("SELECT * FROM donations WHERE id=?", (donation_id,))
    donation = c.fetchone()

    if not donation:
        conn.close()
        return redirect(request.referrer)

    # Fetch volunteer
    c.execute("SELECT * FROM volunteers WHERE phone=?", (donation["volunteer_phone"],))
    volunteer = c.fetchone()

    if volunteer:
        # Mark volunteer available
        c.execute(
            "UPDATE volunteers SET status='Available' WHERE phone=?",
            (volunteer["phone"],),
        )

        # Decrease active tasks safely
        active = volunteer["active_tasks"] if volunteer["active_tasks"] else 0
        new_active = max(active - 1, 0)

        c.execute(
            "UPDATE volunteers SET active_tasks=? WHERE phone=?",
            (new_active, volunteer["phone"]),
        )

    # ✅ Insert donation into past_deliveries
    c.execute(
        """
        INSERT INTO past_deliveries (
            id, food, quantity, district, donor_name, contact,
            volunteer_name, volunteer_phone, timestamp, completed_time
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """,
        (
            donation["id"],
            donation["food"],
            donation["quantity"],
            donation["district"],
            donation["donor_name"],
            donation["contact"],
            donation["volunteer_name"],
            donation["volunteer_phone"],
            donation["timestamp"],
        ),
    )

    # ✅ Keep donation in donations table but mark as completed
    c.execute(
        "UPDATE donations SET pickup_status='Completed', completed_time=datetime('now') WHERE id=?",
        (donation_id,),
    )

    conn.commit()
    conn.close()

    return redirect(request.referrer)


@app.route("/decline_pickup/<int:donation_id>")
def decline_pickup(donation_id):
    conn = sqlite3.connect("donations.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Fetch donation
    c.execute("SELECT * FROM donations WHERE id=?", (donation_id,))
    donation = c.fetchone()
    district = donation["district"]

    # Fetch all volunteers
    c.execute("SELECT * FROM volunteers")
    volunteers = c.fetchall()
    
    declined_volunteer = donation["volunteer_name"]

    matches = match_volunteers(district, volunteers)

    # Remove declined volunteer
    matches = [v for v in matches if v["name"] != declined_volunteer]

    if matches:
        next_volunteer = matches[0]
        print("Next volunteer:", next_volunteer)

        c.execute(
            """
            UPDATE donations
            SET volunteer_name=?, volunteer_phone=?, pickup_status='Assigned'
            WHERE id=?
        """,
            (
                next_volunteer["name"],
                next_volunteer["contact"],
                donation_id,
            ),
        )

        print("Reassigned to:", next_volunteer["name"])

        # Send WhatsApp notification to reassigned volunteer
        try:
            volunteer_phone = next_volunteer["contact"]

            message = f"""
        🚨 New Food Pickup Assigned!

        Hello {next_volunteer['name']},

        A donation has been reassigned to you.

        📍 District: {district}
        🍱 Please check your Volunteer Dashboard for pickup details.

        Thank you for helping reduce food waste! 🙏
        """

            client.messages.create(
                body=message,
                from_="whatsapp:+14155238886",  # Twilio WhatsApp sandbox number
                to=f"whatsapp:+91{volunteer_phone}",
            )

            print("✅ WhatsApp sent to reassigned volunteer")

        except Exception as e:
            print("❌ WhatsApp sending failed:", e)

    else:
        c.execute(
            """
            UPDATE donations
            SET pickup_status='Waiting Volunteer'
            WHERE id=?
        """,
            (donation_id,),
        )
        print("No volunteers available")

    conn.commit()
    conn.close()
    return redirect(request.referrer)


@app.route("/register_volunteer", methods=["POST"])
def register_volunteer():

    name = request.form["name"]
    district = request.form["district"]
    phone = request.form["phone"]
    vehicle = request.form["vehicle"]

    conn = sqlite3.connect("donations.db")
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO volunteers (name,district,phone,vehicle)
        VALUES (?,?,?,?)
    """,
        (name, district, phone, vehicle),
    )

    conn.commit()
    conn.close()

    return redirect("/volunteer_dashboard")


if __name__ == "__main__":
    app.run(debug=True)
