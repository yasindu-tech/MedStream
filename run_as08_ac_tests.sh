#!/bin/bash

API="http://localhost:8080"
echo "=== Step 0: Setup and Forging Role Tokens ==="

PAT_TOKEN=$(/usr/local/bin/docker exec medstream-auth-service-1 python3 -c '
from jose import jwt
from datetime import datetime, timedelta, timezone
print(jwt.encode({"sub": "44444444-4444-4444-8444-444444444444", "role": "patient", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=60)}, "your-super-secret-key-change-in-production", algorithm="HS256"))
')

DOC_TOKEN=$(/usr/local/bin/docker exec medstream-auth-service-1 python3 -c '
from jose import jwt
from datetime import datetime, timedelta, timezone
print(jwt.encode({"sub": "22222222-2222-4222-8222-222222222222", "role": "doctor", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=60)}, "your-super-secret-key-change-in-production", algorithm="HS256"))
')


echo "--- Injecting fresh appointments to test Name Caching (AS-08 Logic) ---"
IDEM=$(uuidgen)
APP_1=$(curl -s -X POST -H "Authorization: Bearer $PAT_TOKEN" -H "Content-Type: application/json" -H "X-Idempotency-Key: $IDEM-1" -d '{"doctor_id":"dddddddd-dddd-4ddd-8ddd-dddddddddddd","clinic_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","date":"2026-11-02","start_time":"10:00","consultation_type":"physical"}' "$API/appointments/appointments/book" | python3 -c "import sys,json; print(json.load(sys.stdin).get('appointment_id'))")
APP_2=$(curl -s -X POST -H "Authorization: Bearer $PAT_TOKEN" -H "Content-Type: application/json" -H "X-Idempotency-Key: $IDEM-2" -d '{"doctor_id":"dddddddd-dddd-4ddd-8ddd-dddddddddddd","clinic_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","date":"2026-11-02","start_time":"11:00","consultation_type":"online"}' "$API/appointments/appointments/book" | python3 -c "import sys,json; print(json.load(sys.stdin).get('appointment_id'))")

echo -e "\n================================================="
echo "AC 1: Patient can view their appointments"
echo "AC 4/5: Appointment shows doctor/patient name, current status, payment_status, etc."
echo "================================================="
curl -s -H "Authorization: Bearer $PAT_TOKEN" "$API/appointments/appointments?page=1&size=2&date=2026-11-02" | python3 -m json.tool

echo -e "\n================================================="
echo "AC 2: Doctor can view appointments assigned strictly to them"
echo "================================================="
curl -s -H "Authorization: Bearer $DOC_TOKEN" "$API/appointments/appointments?page=1&size=2&date=2026-11-02" | python3 -m json.tool

echo -e "\n================================================="
echo "AC 3: Appointments can be filtered safely (Testing 'online' consultation_type)"
echo "================================================="
curl -s -H "Authorization: Bearer $PAT_TOKEN" "$API/appointments/appointments?page=1&size=20&date=2026-11-02&consultation_type=online" | python3 -m json.tool

echo -e "\n================================================="
echo "EDGE CASE 1: Large number of appointments -> paginate results safely"
echo "-> Simulating by capping the size parameter to exactly 1 against total=2."
echo "================================================="
curl -s -H "Authorization: Bearer $PAT_TOKEN" "$API/appointments/appointments?page=1&size=1&date=2026-11-02" | python3 -m json.tool

