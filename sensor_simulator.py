import json
import time
import random

import paho.mqtt.client as mqtt

LOCAL_BROKER = "localhost"
LOCAL_PORT = 1883
PATIENT_ID = "patient-001"
PUBLISH_INTERVAL_SEC = 3


def generate_vitals(pid):
    return {
        "patient_id": pid,
        "heart_rate": round(max(40, min(180, random.gauss(75, 8))), 1),
        "spo2": round(max(80, min(100, random.gauss(97.5, 1.0))), 1),
        "temperature": round(max(35, min(41, random.gauss(36.7, 0.25))), 1),
        "systolic_bp": round(max(80, min(200, random.gauss(112, 10))), 1),
        "resp_rate": round(max(8, min(35, random.gauss(15, 2))), 1),
    }


client = mqtt.Client(client_id="sensor-simulator")
client.connect(LOCAL_BROKER, LOCAL_PORT, keepalive=60)

print(f"[SIM] Publishing simulated vitals for {PATIENT_ID} every {PUBLISH_INTERVAL_SEC}s")
print("[SIM] Press Ctrl+C to stop.\n")

msg_count = 0
try:
    while True:
        payload = generate_vitals(PATIENT_ID)
        topic = f"patients/{PATIENT_ID}/vitals"
        client.publish(topic, json.dumps(payload))
        msg_count += 1
        print(f"[SIM] #{msg_count} -> {topic} : {payload}")
        time.sleep(PUBLISH_INTERVAL_SEC)

except KeyboardInterrupt:
    print("\n[SIM] Shutting down.")
    client.disconnect()