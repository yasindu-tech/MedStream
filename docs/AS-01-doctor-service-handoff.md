# AS-01 · Doctor Service — Implementation Handoff

> **Story:** Search doctors by specialty and availability  
> **Assignee:** Doctor Service developer  
> **Depends on you:** Patient Service will call `GET /internal/doctors/search` on your service. Appointment Service needs to expose `/internal/appointments/booked-slots` (see below).

---

## Context

A patient needs to search for available doctors by specialty, date, consultation type, and clinic. The **Doctor Service** is the source-of-truth for doctor profiles, clinic assignments, and availability schedules. You own the search + slot computation logic.

The Patient Service will act as a thin proxy — it calls your internal endpoint and forwards the results. You don't need to touch the Patient Service.

---

## What You Need to Build

### 1. `GET /internal/doctors/search`

This is an **internal-only** endpoint (not exposed through the nginx gateway) called by the Patient Service.

#### Query Parameters

| Param | Type | Required | Description |
|---|---|---|---|
| `specialty` | `string` | No | Filter by `admin.doctors.specialization` (case-insensitive) |
| `date` | `date` (`YYYY-MM-DD`) | No | Filter availability by day-of-week; also used to compute slot availability |
| `consultation_type` | `string` | No | `physical` or `telemedicine` — filters `admin.doctor_availability.consultation_type` |
| `clinic_id` | `UUID` | No | Restrict results to a specific clinic |

#### Success Response — `200 OK`

Returns an array (empty array `[]` is valid — **do not return 404 when no results**).

```json
[
  {
    "doctor_id": "dddddddd-dddd-4ddd-8ddd-ddddddddddd1",
    "full_name": "Dr. Anura Jayasinghe",
    "specialization": "Cardiology",
    "consultation_type": "physical",
    "clinic_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
    "clinic_name": "Colombo Central Clinic",
    "consultation_fee": null,
    "available_slots": [
      { "start_time": "09:00", "end_time": "09:30" },
      { "start_time": "10:00", "end_time": "10:30" }
    ],
    "has_slots": true
  }
]
```

> **`consultation_fee`** — include this field but it can be `null` for now if the schema doesn't have it yet. We'll wire it later.

---

## Database Tables You'll Query (AdminDB — `medstream_admin`)

All tables live in the `admin` schema. Your service already connects to `medstream_admin`.

### Query Logic (Step-by-Step)

```sql
-- 1. Start with active, verified doctors
SELECT d.*
FROM admin.doctors d
WHERE d.status = 'active'
  AND d.verification_status = 'verified'
  AND (d.specialization ILIKE :specialty OR :specialty IS NULL)

-- 2. Join to get their clinic assignments
JOIN admin.doctor_clinic_assignments dca
  ON dca.doctor_id = d.doctor_id AND dca.status = 'active'

-- 3. Join clinics — only ACTIVE clinics
JOIN admin.clinics c
  ON c.clinic_id = dca.clinic_id AND c.status = 'active'
  AND (c.clinic_id = :clinic_id OR :clinic_id IS NULL)

-- 4. Join availability — filter by day + consultation type
JOIN admin.doctor_availability av
  ON av.doctor_id = d.doctor_id
  AND av.clinic_id = dca.clinic_id
  AND av.status = 'active'
  AND (av.consultation_type = :consultation_type OR :consultation_type IS NULL)
  AND (av.day_of_week = lower(to_char(:date, 'day')) OR :date IS NULL)
```

---

## Slot Computation

For each `(doctor, clinic, availability_row)` matching the query:

1. Call the Appointment Service (see below) to get already-booked slots for that doctor on that date.
2. Generate all slots from `start_time` to `end_time` with `slot_duration` minute intervals.
3. Subtract booked slots (any slot whose `start_time` matches a booked interval).
4. Return the remaining slots as `available_slots`.

**If `date` is not provided** — skip slot computation and return `available_slots: []` for all doctors (the patient hasn't picked a date yet).

**If a doctor has zero remaining slots** — still include them in the response with `available_slots: []` and `has_slots: false`. Do NOT omit them.

### Sorting

Sort final results by earliest `available_slot.start_time` ascending. Doctors with no slots go to the end.

---

## Internal Call to Appointment Service

You need to call the Appointment Service to get booked slots. **This is an internal network call** (within the Docker network, not through the gateway).

```
GET http://appointment-service:8000/internal/appointments/booked-slots
    ?doctor_id=<uuid>
    &clinic_id=<uuid>
    &date=YYYY-MM-DD
```

> ⚠️ **The Appointment Service dev also needs to build this endpoint.** See the section at the bottom of this document.

#### Expected Response from Appointment Service

```json
[
  {
    "doctor_id": "dddddddd-dddd-4ddd-8ddd-ddddddddddd1",
    "clinic_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
    "date": "2026-04-20",
    "start_time": "09:30",
    "end_time": "10:00"
  }
]
```

Booked statuses to consider occupied: `scheduled`, `confirmed`, `in_progress`. Ignore `cancelled` and `completed`.

---

## Edge Cases — Enforce These

| Case | Expected Behaviour |
|---|---|
| `verification_status != 'verified'` | Exclude from results entirely |
| `status != 'active'` (doctor) | Exclude from results entirely |
| Clinic `status != 'active'` | Do not include slots from that clinic |
| Doctor has availability record but all slots booked | Include doctor with `available_slots: []`, `has_slots: false` |
| No doctors match filters | Return `200 OK` with `[]` — **never return `404`** |
| `date` not provided | Skip slot computation; return doctor cards with `available_slots: []` |

---

## Files to Create / Modify in Your Service

```
doctor-service/
├── app/
│   ├── models/
│   │   └── doctor.py          # SQLAlchemy models: Doctor, DoctorClinicAssignment,
│   │                          #   DoctorAvailability, Clinic
│   ├── schemas/
│   │   └── doctor_search.py   # Pydantic: SlotItem, DoctorSearchResult
│   ├── routers/
│   │   └── internal.py        # Router for /internal/* (no auth required)
│   └── services/
│       ├── doctor_search.py   # Search + slot computation logic
│       └── appointment_client.py  # httpx call to appointment-service
└── main.py                    # Register internal router
```

### Router registration in `main.py`

```python
from fastapi import FastAPI
from app.routers.internal import router as internal_router

app = FastAPI(title="doctor-service", version="0.1.0")
app.include_router(internal_router, prefix="/internal")

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok", "service": "doctor-service"}
```

---

## What Appointment Service Needs to Build

> **Pass this to the Appointment Service developer.**

### `GET /internal/appointments/booked-slots`

#### Query Parameters

| Param | Type | Required |
|---|---|---|
| `doctor_id` | UUID | Yes |
| `clinic_id` | UUID | Yes |
| `date` | `YYYY-MM-DD` | Yes |

#### Query (PatientCareDB — `patientcare` schema)

```sql
SELECT doctor_id, clinic_id, appointment_date AS date, start_time, end_time
FROM patientcare.appointments
WHERE doctor_id = :doctor_id
  AND clinic_id = :clinic_id
  AND appointment_date = :date
  AND status IN ('scheduled', 'confirmed', 'in_progress')
```

#### Response — `200 OK`

```json
[
  {
    "doctor_id": "uuid",
    "clinic_id": "uuid",
    "date": "2026-04-20",
    "start_time": "09:30",
    "end_time": "10:00"
  }
]
```

Return `[]` if none found. No auth required (internal call).

---

## Testing Your Endpoint

Once running with `docker-compose up doctor-service appointment-service`:

```bash
# Should return 2 doctors from seed data
curl "http://localhost:8007/internal/doctors/search?specialty=Cardiology"

# Should filter by day (monday)
curl "http://localhost:8007/internal/doctors/search?date=2026-04-21"

# Should return empty list (not an error)
curl "http://localhost:8007/internal/doctors/search?specialty=Neurology"

# Should exclude booked slot 09:30 for Dr. Anura on 2026-04-20
curl "http://localhost:8007/internal/doctors/search?specialty=Cardiology&date=2026-04-20"
```

---

## Seed Data Reference

The existing seed data in `infrastructure/db/init-admin-db.sql` already has:

| Doctor | Specialization | Clinic | Day | Hours | Type |
|---|---|---|---|---|---|
| Dr. Anura Jayasinghe | Cardiology | Colombo Central | Monday | 09:00–13:00 | physical |
| Dr. Anura Jayasinghe | Cardiology | Colombo Central | Wednesday | 14:00–17:00 | telemedicine |
| Dr. Nadee Fernando | Dermatology | Kandy Family Care | Tuesday | 10:00–15:00 | physical |

And in `init-patientcare-db.sql`:
- Appointment booked for Kamal Perera: `2026-04-20` (Monday) at `09:30–10:00` with Dr. Anura at Colombo Central (status: `scheduled`)

---

## Questions / Contact

If the slot computation or internal API contract needs clarification, sync with the Patient Service dev before building. The response schema above is the agreed contract — do not change field names without notifying the Patient Service team.
