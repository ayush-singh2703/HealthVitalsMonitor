import json
import random
import time

import paho.mqtt.client as mqtt

BROKER = "localhost"
PORT = 1883
PATIENT = "patient-001"
TOPIC = f"patients/{PATIENT}/vitals"
INTERVAL = 3

client = mqtt.Client(client_id="vitals-simulator")
client.connect(BROKER, PORT, keepalive=60)
client.loop_start()

print(f"Publishing vitals for {PATIENT} to local topic {TOPIC}")
print("Press Ctrl+C to stop\n")

msg_count = 0

try:
    while True:
        payload = {
            "patient_id": PATIENT,
            "heart_rate": round(random.uniform(50, 140), 1),
            "spo2": round(random.uniform(85, 100), 1),
            "temperature": round(random.uniform(35.0, 40.5), 1),
            "systolic_bp": round(random.uniform(90, 180), 1),
            "resp_rate": round(random.uniform(10, 30), 1),
            "msg_count": msg_count,
        }

        client.publish(TOPIC, json.dumps(payload), qos=1)

        print(
            f"[PUB #{msg_count}] "
            f"HR={payload['heart_rate']}  "
            f"SpO2={payload['spo2']}  "
            f"Temp={payload['temperature']}  "
            f"BP={payload['systolic_bp']}  "
            f"RR={payload['resp_rate']}"
        )

        msg_count += 1
        time.sleep(INTERVAL)

except KeyboardInterrupt:
    print(f"\nStopped. Published {msg_count} readings.")
    client.loop_stop()
    client.disconnect()
