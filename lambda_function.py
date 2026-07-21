import json, boto3, time
from decimal import Decimal

dynamodb = boto3.resource("dynamodb")
vitals_tbl = dynamodb.Table("PatientVitals")
alert_tbl = dynamodb.Table("CriticalAlerts")

def lambda_handler(event, context):
    for record in event["Records"]:
        payload = json.loads(record["body"])

        item = {
            "patient_id": payload["patient_id"],
            "timestamp": Decimal(str(int(time.time() * 1000))),
            "heart_rate": Decimal(str(payload.get("heart_rate", 0))),
            "spo2": Decimal(str(payload.get("spo2", 0))),
            "temperature": Decimal(str(payload.get("temperature", 0))),
            "systolic_bp": Decimal(str(payload.get("systolic_bp", 0))),
            "resp_rate": Decimal(str(payload.get("resp_rate", 0))),
            "severity": payload.get("severity", "normal"),
        }

        vitals_tbl.put_item(Item=item)

        if item["severity"] == "critical":
            alert_tbl.put_item(Item=item)

    return {"statusCode": 200, "batchItemFailures": []}