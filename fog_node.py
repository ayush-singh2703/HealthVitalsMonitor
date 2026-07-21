import json
import ssl
import time
import logging
from datetime import datetime

import paho.mqtt.client as mqtt
import redis


LOCAL_BROKER = "localhost"
LOCAL_PORT = 1883
LOCAL_TOPIC = "patients/+/vitals"


AWS_ENDPOINT = "a3hjthv0j5udjt-ats.iot.us-east-1.amazonaws.com"
AWS_PORT = 8883
CA_CERT = "certs/AmazonRootCA1.pem"
CERT = "certs/device_cert.pem.crt"
KEY = "certs/device_private.pem.key"


THRESHOLDS = {
    "heart_rate": (60, 100),
    "spo2": (94, 100),
    "temperature": (36.1, 37.5),
    "systolic_bp": (90, 140),
    "resp_rate": (12, 20),
}

# Local "monitor" alert logging — independent of cloud pipeline
logging.basicConfig(
    filename="critical_alerts.log",
    level=logging.WARNING,
    format="%(asctime)s %(message)s"
)


r = redis.Redis(host="localhost", port=6379, decode_responses=True)


aws_client = mqtt.Client(client_id="fog-node-forwarder")
aws_client.tls_set(
    ca_certs=CA_CERT,
    certfile=CERT,
    keyfile=KEY,
    tls_version=ssl.PROTOCOL_TLSv1_2,
)


def on_aws_connect(client, userdata, flags, rc):
    print(f"[FOG] Connected to AWS IoT Core, rc={rc}")


aws_client.on_connect = on_aws_connect
aws_client.connect(AWS_ENDPOINT, AWS_PORT, keepalive=60)
aws_client.loop_start()
time.sleep(2)


def classify(vitals):
    status = "normal"

    for key, (low, high) in THRESHOLDS.items():
        val = vitals.get(key)

        if val is None:
            continue

        if val < low * 0.85 or val > high * 1.15:
            return "critical"
        if val < low or val > high:
            status = "warning"

    return status


def handle_local_alert(vitals, severity):
    """Instant local 'bedside monitor' alert — fires before any cloud call."""
    if severity == "critical":
        ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        msg = (f"CRITICAL ALERT | patient={vitals.get('patient_id')} "
               f"HR={vitals.get('heart_rate')} SpO2={vitals.get('spo2')} "
               f"Temp={vitals.get('temperature')} BP={vitals.get('systolic_bp')} "
               f"RR={vitals.get('resp_rate')}")
        print(f"\033[91m🚨 {msg} at {ts}\033[0m")
        logging.warning(msg)
    elif severity == "warning":
        print(f"\033[93m⚠️  WARNING | {vitals.get('patient_id')} — vitals out of range\033[0m")


def on_local_message(client, userdata, msg):
    local_start = datetime.now()

    vitals = json.loads(msg.payload.decode())

    patient_id = vitals.get("patient_id", "unknown")
    severity = classify(vitals)

    vitals["severity"] = severity
    vitals["ts"] = int(time.time())

    # 1. Local monitor alert — fires immediately, no cloud dependency
    handle_local_alert(vitals, severity)
    local_end = datetime.now()
    local_latency_ms = (local_end - local_start).total_seconds() * 1000
    print(f"[TIMING] Local detection+alert took {local_latency_ms:.2f} ms")

    # Cache latest state in Redis
    r.hset(
        f"patient:{patient_id}:state",
        mapping={k: str(v) for k, v in vitals.items()},
    )
    r.expire(f"patient:{patient_id}:state", 30)

    # Rolling window (last 10 readings)
    r.lpush(f"patient:{patient_id}:history", json.dumps(vitals))
    r.ltrim(f"patient:{patient_id}:history", 0, 9)

    print(
        f"[FOG] {patient_id}  "
        f"severity={severity}  "
        f"HR={vitals.get('heart_rate')}  "
        f"SpO2={vitals.get('spo2')}"
    )

    if severity == "critical":
        r.publish("vitals:alerts", json.dumps(vitals))
        print(f"[ALERT] Published critical alert to Redis channel for {patient_id}")

    # 2. Forward to AWS IoT Core — separate, slower cloud path
    aws_topic = f"patients/{patient_id}/vitals"
    aws_client.publish(aws_topic, json.dumps(vitals), qos=1)


local_client = mqtt.Client(client_id="fog-node-subscriber")
local_client.on_message = on_local_message


local_client.connect(LOCAL_BROKER, LOCAL_PORT, keepalive=60)
local_client.subscribe(LOCAL_TOPIC)


print(f"[FOG] Subscribed to local topic {LOCAL_TOPIC}")
print("[FOG] Fog node running. Press Ctrl+C to stop.\n")


try:
    local_client.loop_forever()

except KeyboardInterrupt:
    print("\n[FOG] Shutting down.")
    aws_client.loop_stop()
    aws_client.disconnect()