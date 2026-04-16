#!/bin/bash

API="http://localhost:8080"
echo "=== Setup: Forging Role Tokens ==="

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

echo -e "\n=== 1. AC: Patient Viewing History (Validating 'doctor_name' + 'clinic_name' Caching) ==="
curl -s -H "Authorization: Bearer $PAT_TOKEN" "$API/appointments/appointments?page=1&size=5" | python3 -m json.tool

echo -e "\n=== 2. AC: Filter application seamlessly dropping parameters via Date ==="
# Date where we previously booked the 2026-08-01 slot
curl -s -H "Authorization: Bearer $PAT_TOKEN" "$API/appointments/appointments?page=1&size=5&date=2026-08-01" | python3 -m json.tool

echo -e "\n=== 3. AC: Doctor natively pulling their own exact constraints ==="
curl -s -H "Authorization: Bearer $DOC_TOKEN" "$API/appointments/appointments?page=1&size=20&status=cancelled" | python3 -m json.tool

