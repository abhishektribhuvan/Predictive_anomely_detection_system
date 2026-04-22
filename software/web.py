import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import time

st.set_page_config(page_title="Motor Diagnostic UI", layout="wide")
st.title("⚙️ B2B Motor Diagnostic Dashboard")

API_URL = "http://127.0.0.1:8000"

# ---- Initialize session state ----
if "live_running" not in st.session_state:
    st.session_state.live_running = False
if "data_x" not in st.session_state:
    st.session_state.data_x = []
if "data_y" not in st.session_state:
    st.session_state.data_y = []
if "data_z" not in st.session_state:
    st.session_state.data_z = []
if "avg_x" not in st.session_state:
    st.session_state.avg_x = 0
if "avg_y" not in st.session_state:
    st.session_state.avg_y = 0
if "avg_z" not in st.session_state:
    st.session_state.avg_z = 0

MAX_POINTS = 100  # scrolling window size (like Task Manager)

col1, col2, col3 = st.columns(3)

# ==========================================
# ACTION 1: CALIBRATE (1000 Readings)
# ==========================================
with col1:
    st.subheader("Step 1: Calibration")
    if st.button("▶ Action 1: Read 1000 Values"):
        with st.spinner("Recording 1000 high-speed readings (Takes ~20 sec)..."):
            try:
                res = requests.post(f"{API_URL}/api/action1_calibrate", timeout=60)
                if res.status_code == 200:
                    st.success("✅ Calibration Saved to CSV!")
                else:
                    st.error(f"Backend error: {res.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Backend not running! Start `uvicorn main:app` first.")

# ==========================================
# ACTION 3: VIEW DISTRIBUTION
# ==========================================
with col3:
    st.subheader("Step 2: Distribution")
    if st.button("▶ Action 3: Show Distribution"):
        try:
            res = requests.get(f"{API_URL}/api/action3_distribution", timeout=10)
            if res.status_code == 200:
                st.image(res.content, caption="1000-Reading Bell Curves")
            else:
                st.error(f"Backend error: {res.status_code}")
        except requests.exceptions.ConnectionError:
            st.error("❌ Backend not running!")

st.divider()

# ==========================================
# ACTION 2: LIVE TASK MANAGER GRAPHS
# ==========================================
st.subheader("Step 3: Live Task Manager View")

col_start, col_stop = st.columns(2)
with col_start:
    if st.button("▶ Start Live Stream"):
        st.session_state.live_running = True
        st.session_state.data_x = []
        st.session_state.data_y = []
        st.session_state.data_z = []
with col_stop:
    if st.button("⏹ Stop Live Stream"):
        st.session_state.live_running = False


def make_task_manager_chart(data_list, avg_val, title, live_color, axis_label):
    """Create a Plotly chart that looks like Windows Task Manager."""
    fig = go.Figure()

    # Live scrolling line
    fig.add_trace(go.Scatter(
        y=data_list,
        mode='lines',
        name=f'Live {axis_label}',
        line=dict(color=live_color, width=2),
        fill='tozeroy',
        fillcolor=live_color.replace('1)', '0.15)'),  # semi-transparent fill
    ))

    # Constant average line from calibration
    if avg_val != 0:
        fig.add_hline(
            y=avg_val,
            line_dash="dash",
            line_color="white",
            line_width=2,
            annotation_text=f"Avg: {avg_val:.2f}",
            annotation_font_color="white",
            annotation_font_size=12,
        )

    fig.update_layout(
        title=dict(text=title, font=dict(color="white", size=14)),
        paper_bgcolor="#1a1a2e",
        plot_bgcolor="#16213e",
        font=dict(color="#a0a0a0"),
        height=280,
        margin=dict(l=40, r=20, t=40, b=30),
        showlegend=False,
        xaxis=dict(
            showgrid=True,
            gridcolor="#2a2a4a",
            gridwidth=1,
            showticklabels=False,
            range=[0, MAX_POINTS],
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="#2a2a4a",
            gridwidth=1,
        ),
    )
    return fig


# Placeholders for graphs
graph_col1, graph_col2, graph_col3 = st.columns(3)
ph_x = graph_col1.empty()
ph_y = graph_col2.empty()
ph_z = graph_col3.empty()
status_ph = st.empty()

if st.session_state.live_running:
    try:
        res = requests.get(f"{API_URL}/api/action2_live", timeout=5).json()

        live = res["live"]
        avg = res["averages"]

        # Store averages
        st.session_state.avg_x = avg["avg_x"]
        st.session_state.avg_y = avg["avg_y"]
        st.session_state.avg_z = avg["avg_z"]

        # Append new live data, cap at MAX_POINTS
        st.session_state.data_x.append(live["x"])
        st.session_state.data_y.append(live["y"])
        st.session_state.data_z.append(live["z"])

        st.session_state.data_x = st.session_state.data_x[-MAX_POINTS:]
        st.session_state.data_y = st.session_state.data_y[-MAX_POINTS:]
        st.session_state.data_z = st.session_state.data_z[-MAX_POINTS:]

        # Draw Task Manager-style charts
        ph_x.plotly_chart(
            make_task_manager_chart(
                st.session_state.data_x, st.session_state.avg_x,
                "X-Axis", "rgba(255, 60, 60, 1)", "X"
            ),
            use_container_width=True, key="chart_x"
        )
        ph_y.plotly_chart(
            make_task_manager_chart(
                st.session_state.data_y, st.session_state.avg_y,
                "Y-Axis", "rgba(60, 255, 60, 1)", "Y"
            ),
            use_container_width=True, key="chart_y"
        )
        ph_z.plotly_chart(
            make_task_manager_chart(
                st.session_state.data_z, st.session_state.avg_z,
                "Z-Axis", "rgba(60, 120, 255, 1)", "Z"
            ),
            use_container_width=True, key="chart_z"
        )

        status_ph.caption(
            f"📡 Live — X: {live['x']:.2f}  |  Y: {live['y']:.2f}  |  Z: {live['z']:.2f}  "
            f"(Avg X: {st.session_state.avg_x:.2f}, Y: {st.session_state.avg_y:.2f}, Z: {st.session_state.avg_z:.2f})"
        )

        # Wait 1 second then re-run to fetch next reading
        time.sleep(1)
        st.rerun()

    except requests.exceptions.ConnectionError:
        status_ph.error("❌ Backend not running! Start `uvicorn main:app` first.")
        st.session_state.live_running = False
    except Exception as e:
        status_ph.error(f"❌ Error: {e}")
        st.session_state.live_running = False
else:
    # Show empty placeholder charts when not streaming
    ph_x.plotly_chart(
        make_task_manager_chart([], 0, "X-Axis", "rgba(255, 60, 60, 1)", "X"),
        use_container_width=True, key="chart_x_idle"
    )
    ph_y.plotly_chart(
        make_task_manager_chart([], 0, "Y-Axis", "rgba(60, 255, 60, 1)", "Y"),
        use_container_width=True, key="chart_y_idle"
    )
    ph_z.plotly_chart(
        make_task_manager_chart([], 0, "Z-Axis", "rgba(60, 120, 255, 1)", "Z"),
        use_container_width=True, key="chart_z_idle"
    )
    status_ph.caption("⏸ Live stream stopped. Click 'Start Live Stream' to begin.")