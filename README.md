# HealthVitalsMonitor
A setup where I simulate the health sensor vitals and injest that into fog node which is running in EC2, on the basis of thresholds which are realistically defined in fog node, the levels are classified which are further sent to  SQS and to lambda to save the patient data in dynamo DB.
