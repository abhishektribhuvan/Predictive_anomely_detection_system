import serial
import json
import csv
import threading
import time
import os
import io
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow cross-origin requests from Streamlit's embedded iframe
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURATION ---
SERIAL_PORT = "COM3"  # <--- CHANGE TO YOUR ESP32 PORT
BAUD_RATE = 115200
CSV_FILE = "calibration_1000.csv"

# Global state variables
latest_reading = {"x": 0.0, "y": 0.0, "z": 0.0}
is_calibrating = False
calibration_count = 0

# Rolling Z-score history buffer (stores dicts with timestamp & z-scores)
MAX_HISTORY = 100
zscore_history = []  # list of {"tick": int, "x": float, "y": float, "z": float, "anomaly": bool}
zscore_tick = 0

# Cached calibration stats (recomputed on each calibration)
cal_stats = {"x": {"mean": 0, "std": 0}, "y": {"mean": 0, "std": 0}, "z": {"mean": 0, "std": 0}}

# --- BACKGROUND USB LISTENER ---
def serial_worker():
    global latest_reading, is_calibrating, calibration_count
    
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"[*] Connected to {SERIAL_PORT}")
    except Exception:
        print(f"[!] Could not open {SERIAL_PORT}. Close Arduino IDE!")
        return

    while True:
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if line.startswith('{') and line.endswith('}'):
                    data = json.loads(line)
                    # Store absolute values so negatives don't cancel out
                    latest_reading = {
                        "x": abs(data['x']),
                        "y": abs(data['y']),
                        "z": abs(data['z'])
                    }
                    
                    # ACTION 1 LOGIC: If triggered, save absolute values to CSV until we hit 1000
                    if is_calibrating and calibration_count < 1000:
                        with open(CSV_FILE, mode='a', newline='') as file:
                            csv.writer(file).writerow([abs(data['x']), abs(data['y']), abs(data['z'])])
                        calibration_count += 1
                        if calibration_count >= 1000:
                            is_calibrating = False # Stop recording when done
                            print("[*] Calibration Complete: 1000 readings saved.")
        except Exception:
            time.sleep(0.01)

@app.on_event("startup")
def startup():
    threading.Thread(target=serial_worker, daemon=True).start()

# --- ACTION 1: TRIGGER CALIBRATION ---
@app.post("/api/action1_calibrate")
def trigger_calibration():
    global is_calibrating, calibration_count
    
    # Wipe the old CSV and start fresh
    with open(CSV_FILE, mode='w', newline='') as file:
        csv.writer(file).writerow(["x", "y", "z"])
        
    calibration_count = 0
    is_calibrating = True
    
    # Wait until the background thread finishes reading 1000 values
    while is_calibrating:
        time.sleep(0.5)

    # Refresh cached stats and reset Z-score history after new calibration
    _refresh_cal_stats()
    global zscore_history, zscore_tick
    zscore_history = []
    zscore_tick = 0

    return {"message": "Successfully recorded 1000 readings"}

# --- ACTION 2: GET LIVE DATA & AVERAGES ---
@app.get("/api/action2_live")
def get_live_data():
    averages = {"avg_x": 0, "avg_y": 0, "avg_z": 0}
    
    # Calculate the flat line averages from the CSV
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        if not df.empty:
            averages = {
                "avg_x": df['x'].abs().mean(),
                "avg_y": df['y'].abs().mean(),
                "avg_z": df['z'].abs().mean()
            }
            
    return {"live": latest_reading, "averages": averages}

# --- ACTION 3: GET DISTRIBUTION GRAPHS (X, Y, Z — 3 separate plots) ---
@app.get("/api/action3_distribution")
def get_distribution():
    if not os.path.exists(CSV_FILE):
        return Response(content="No data", status_code=404)

    df = pd.read_csv(CSV_FILE)
    if df.empty:
        return Response(content="No data", status_code=404)

    sns.set_theme(style="darkgrid")
    fig, axes = plt.subplots(1, 3, figsize=(18, 6))

    axis_config = [
        ("X-Axis", df['x'], "cornflowerblue", axes[0]),
        ("Y-Axis", df['y'], "#2ecc71", axes[1]),
        ("Z-Axis", df['z'], "#e74c3c", axes[2]),
    ]

    for title, data, color, ax in axis_config:
        mu = data.mean()
        sigma = data.std()

        sns.histplot(data, kde=True, ax=ax, color=color, edgecolor='white', linewidth=0.5, bins=40)
        ax.set_title(f"Distribution: {title}\n(μ={mu:.2f}, σ={sigma:.2f})", fontsize=13, fontweight='bold')
        ax.set_xlabel("Sensor Value", fontsize=11)
        ax.set_ylabel("Frequency", fontsize=11)

        # Mean line
        ax.axvline(mu, color='black', linestyle='-', linewidth=1.5, label=f"Mean: {mu:.2f}")
        # ±3σ anomaly boundaries
        ax.axvline(mu + 3*sigma, color='orange', linestyle='--', linewidth=2, label=f"+3σ: {mu+3*sigma:.2f}")
        ax.axvline(mu - 3*sigma, color='orange', linestyle='--', linewidth=2, label=f"-3σ: {mu-3*sigma:.2f}")

        ax.legend(fontsize=9, loc="upper right")

    fig.suptitle("Vibration Distribution — 1000 Calibration Readings", fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches='tight')
    plt.close()
    buf.seek(0)

    return Response(content=buf.getvalue(), media_type="image/png")

# --- Helper: Recompute calibration stats from CSV ---
def _refresh_cal_stats():
    """Load the calibration CSV and cache μ, σ for each axis."""
    global cal_stats
    if not os.path.exists(CSV_FILE):
        return False
    df = pd.read_csv(CSV_FILE)
    if df.empty:
        return False
    for axis in ['x', 'y', 'z']:
        cal_stats[axis] = {
            "mean": float(df[axis].abs().mean()),
            "std":  float(df[axis].abs().std()),
        }
    return True


# --- ACTION 4: ANOMALY DETECTION (Z-Score based) ---
@app.get("/api/action4_anomaly")
def detect_anomaly():
    """
    Compare the current live reading against the calibration baseline.

    Z-Score method:
        Z = (|live_value| − μ) / σ
    where μ and σ are computed from the absolute calibration readings.

    Decision rule:
        |Z| > 3  →  Anomaly on that axis.

    Also appends the result to a rolling history buffer so the
    frontend can plot Z-scores over time.
    """
    global zscore_tick

    # Ensure calibration stats are loaded
    if cal_stats['x']['std'] == 0 and cal_stats['y']['std'] == 0:
        if not _refresh_cal_stats():
            return {"error": "No calibration data. Run Action 1 first."}

    live = latest_reading  # already absolute from serial_worker

    results = {}
    overall_anomaly = False
    history_entry = {"tick": zscore_tick}

    for axis in ['x', 'y', 'z']:
        mu    = cal_stats[axis]["mean"]
        sigma = cal_stats[axis]["std"]
        value = abs(live[axis])  # ensure absolute

        if sigma == 0:
            z_score = 0.0
        else:
            z_score = (value - mu) / sigma

        is_anomaly = abs(z_score) > 3.0

        results[axis] = {
            "value":     round(value, 4),
            "mean":      round(mu, 4),
            "std":       round(sigma, 4),
            "z_score":   round(z_score, 4),
            "is_anomaly": is_anomaly,
            "upper_bound": round(mu + 3 * sigma, 4),
            "lower_bound": round(max(mu - 3 * sigma, 0), 4),  # clamp to 0 for abs values
        }

        history_entry[axis] = round(z_score, 4)

        if is_anomaly:
            overall_anomaly = True

    history_entry["anomaly"] = overall_anomaly

    # Append to rolling buffer
    zscore_history.append(history_entry)
    if len(zscore_history) > MAX_HISTORY:
        zscore_history.pop(0)
    zscore_tick += 1

    return {
        "axes": results,
        "overall_anomaly": overall_anomaly,
        "threshold": 3.0,
        "history": zscore_history,   # full rolling window for charting
    }