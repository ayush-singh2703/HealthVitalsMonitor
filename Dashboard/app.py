import streamlit as st
import boto3, pandas as pd
from boto3.dynamodb.conditions import Key
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
import time

st.set_page_config(page_title="Patient Monitor Dashboard", layout="wide")

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
vitals_tbl = dynamodb.Table("PatientVitals")
alert_tbl = dynamodb.Table("CriticalAlerts")

PATIENT_ID = "patient-001"
VITALS = ["heart_rate", "spo2", "temperature", "systolic_bp", "resp_rate"]
UNITS = {"heart_rate": "bpm", "spo2": "%", "temperature": "°C", "systolic_bp": "mmHg", "resp_rate": "breaths/min"}
COLOR_MAP = {"normal": "green", "warning": "orange", "critical": "red"}
TIME_WINDOW_HOURS = 1


@st.cache_data(ttl=5)
def fetch_vitals():
    resp = vitals_tbl.query(KeyConditionExpression=Key("patient_id").eq(PATIENT_ID))
    df = pd.DataFrame(resp["Items"])
    if df.empty:
        return df

    df["timestamp"] = df["timestamp"].astype(float)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    for c in VITALS:
        if c in df.columns:
            df[c] = df[c].astype(float)
    df = df.sort_values("datetime")

    cutoff = pd.Timestamp.now(tz="UTC") - timedelta(hours=TIME_WINDOW_HOURS)
    df = df[df["datetime"] >= cutoff]
    return df


@st.cache_data(ttl=5)
def fetch_alerts():
    resp = alert_tbl.query(KeyConditionExpression=Key("patient_id").eq(PATIENT_ID))
    df = pd.DataFrame(resp["Items"])
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"].astype(float), unit="ms", utc=True)
    df = df.sort_values("timestamp")

    cutoff = pd.Timestamp.now(tz="UTC") - timedelta(hours=TIME_WINDOW_HOURS)
    df = df[df["timestamp"] >= cutoff]
    return df


def plot_vital(df, vital, unit):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["datetime"], y=df[vital],
        mode="lines",
        line=dict(color="lightgray", width=1),
        name=vital,
        showlegend=False
    ))
    for sev, color in COLOR_MAP.items():
        sub = df[df["severity"] == sev]
        if not sub.empty:
            fig.add_trace(go.Scatter(
                x=sub["datetime"], y=sub[vital],
                mode="markers",
                marker=dict(color=color, size=6),
                name=sev
            ))
    fig.update_layout(
        title=f"{vital.replace('_', ' ').title()} ({unit})",
        xaxis_title="Time",
        yaxis_title=vital,
        height=320
    )
    return fig


st.title(f"Patient Monitor — {PATIENT_ID}")
st.caption(f"Fog node handles instant local alerts; cloud (DynamoDB) stores history for trend review and audit. "
           f"Showing last {TIME_WINDOW_HOURS} hour(s) of data, auto-refreshes every 5s.")

df = fetch_vitals()
alerts_df = fetch_alerts()

if df.empty:
    st.warning("No recent data found. Confirm sensor_simulator.py and fog_node.py are running, "
               "and that data has been written within the last hour.")
else:
    latest = df.iloc[-1]
    severity = latest.get("severity", "normal")
    color = COLOR_MAP.get(severity, "gray")
    st.markdown(f"### Current status: :{color}[{severity.upper()}]")

    cols = st.columns(len(VITALS))
    for i, v in enumerate(VITALS):
        if v in df.columns:
            cols[i].metric(v.replace("_", " ").title(), f"{latest[v]:.1f} {UNITS[v]}")

    st.divider()

    st.header("Severity over time")
    sev_map = {"normal": 0, "warning": 1, "critical": 2}
    df["severity_num"] = df["severity"].map(sev_map)
    fig_sev = px.area(df, x="datetime", y="severity_num",
                       title="Severity level trend (0=normal, 1=warning, 2=critical)")
    fig_sev.update_yaxes(tickvals=[0, 1, 2], ticktext=["Normal", "Warning", "Critical"])
    st.plotly_chart(fig_sev, use_container_width=True)

    st.divider()

    st.header("Vitals trend")
    left, right = st.columns(2)
    for i, v in enumerate(VITALS):
        if v not in df.columns:
            continue
        target = left if i % 2 == 0 else right
        fig = plot_vital(df, v, UNITS[v])
        target.plotly_chart(fig, use_container_width=True)

st.divider()

st.header("Critical alert frequency")
if not alerts_df.empty:
    alerts_df["hour"] = alerts_df["timestamp"].dt.floor("h")
    freq = alerts_df.groupby("hour").size().reset_index(name="alerts")
    fig_bar = px.bar(freq, x="hour", y="alerts", title="Critical alerts per hour")
    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("Recent critical alerts")
    display_cols = ["timestamp"] + [v for v in VITALS if v in alerts_df.columns]
    st.dataframe(
        alerts_df[display_cols].sort_values("timestamp", ascending=False).head(10),
        use_container_width=True
    )
else:
    st.info("No critical alerts recorded in the selected time window.")

time.sleep(5)
st.rerun()