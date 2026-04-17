# Telemedicine Frontend API Guide

## 1. API Base and Routing

All frontend traffic should go through the API gateway.

- Base URL (local): `http://localhost:8080`
- Telemedicine routes: `/telemedicine/...`
- Appointment routes used by telemedicine workflows: `/appointments/...`

Do not call service-internal endpoints (`/internal/...`) from the browser.

## 2. Authentication Model

Use standard access-token authentication for user-facing APIs.

1. Login:
   - `POST /auth/login`
2. Send access token in every protected request:
   - `Authorization: Bearer <ACCESS_TOKEN>`

### Join Token vs Access Token

- Access token: used to request a telemedicine join link.
- Join token: embedded in the generated join URL and used only for join-token validation.

## 3. Role Behavior in UI

Frontend role guards should reflect backend scope checks.

- `patient`
  - Can request join link only for own appointment.
- `doctor`
  - Can request join link only for own appointment.
- `staff`, `admin`
  - Can request join links for operational workflows.
- `admin`
  - Can connect and monitor Google OAuth integration.

If ownership or role checks fail, backend returns `403`.

## 4. Telemedicine API Endpoints

### 4.1 Create Join Link

- Method: `POST /telemedicine/sessions/join-link`
- Auth: required
- Body:

```json
{
  "appointment_id": "UUID"
}
```

- Response:

```json
{
  "session_id": "UUID",
  "join_url": "https://...?...token=...",
  "expires_in_seconds": 1800
}
```

### 4.2 Validate Join Token

- Method: `GET /telemedicine/sessions/validate`
- Auth: join token in header
- Header:
  - `Authorization: Bearer <JOIN_TOKEN>`

- Response:

```json
{
  "session_id": "UUID",
  "appointment_id": "UUID",
  "status": "scheduled",
  "provider_name": "MedStream Meet",
  "session_version": 1,
  "token_version": 1
}
```

### 4.3 Google OAuth Status (Admin)

- Method: `GET /telemedicine/auth/google/status`
- Auth: admin

Disconnected example:

```json
{
  "connected": false,
  "provider": "google_meet"
}
```

Connected example:

```json
{
  "connected": true,
  "provider": "google_meet",
  "account_email": "telemedicine@yourorg.com",
  "scope": "https://www.googleapis.com/auth/meetings.space.created",
  "updated_at": "2026-04-17T00:00:00Z"
}
```

### 4.4 Start Google OAuth Connect (Admin)

- Method: `GET /telemedicine/auth/google/login`
- Auth: admin
- Behavior:
  - Returns redirect (`307`) to Google OAuth consent URL.
  - Frontend should navigate browser to this endpoint.

### 4.5 Google OAuth Callback

- Method: `GET /telemedicine/auth/google/callback?code=...&state=...`
- Behavior:
  - Called by Google after consent.
  - Backend exchanges code for token and stores refresh token.

## 5. Appointment APIs Used by Telemedicine UI

### 5.1 Mark Technical Failure (AS-16)

- Method: `POST /appointments/appointments/{appointment_id}/technical-failure`
- Auth: `doctor`, `patient`, `staff`, `admin` (with ownership constraints)
- Body:

```json
{
  "reason": "Provider outage detected"
}
```

### 5.2 Mark Arrived

- Method: `POST /appointments/appointments/{appointment_id}/arrived`

### 5.3 Mark Completed

- Method: `POST /appointments/appointments/{appointment_id}/complete`

### 5.4 Admin Mark No-Show (AS-15 Operational)

- Method: `POST /appointments/admin/appointments/{appointment_id}/no-show`
- Body:

```json
{
  "reason": "No join after grace period"
}
```

### 5.5 Dashboard Metrics (AS-27)

- Method: `GET /appointments/admin/statistics`
- Auth: `admin`, `staff`
- Supported filters:
  - `date_from`
  - `date_to`
  - `clinic_id`
  - `doctor_id`
  - `outcome`

- Response:

```json
{
  "total_bookings": 0,
  "total_cancellations": 0,
  "total_no_shows": 0,
  "total_completed": 0,
  "total_failed_sessions": 0,
  "average_duration_minutes": null
}
```

### 5.6 Live Telemedicine Statuses (AS-27)

- Method: `GET /appointments/admin/telemedicine/live-statuses`
- Auth: `admin`, `staff`
- Supported filters:
  - `page`
  - `size`
  - `clinic_id`
  - `doctor_id`
  - `date_from`
  - `date_to`
  - `outcome`

## 6. Recommended Frontend Flows

### 6.1 Patient/Doctor Join Flow

1. Load appointment details in UI.
2. Call join-link API.
3. Open `join_url` in new tab.
4. Optional: validate join token before navigation.

### 6.2 Technical Failure Flow

1. Show "Mark Technical Failure" action during session.
2. Capture failure reason.
3. Call technical-failure endpoint.
4. Update appointment status to `technical_failed`.
5. Display reschedule recommendation UI if desired.

### 6.3 Google Connect Flow (Admin)

1. Query OAuth status endpoint.
2. If disconnected, show "Connect Google" button.
3. Button navigates to login endpoint.
4. After callback, refresh status.

### 6.4 Operational Dashboard Flow

1. Load metrics and live statuses.
2. Apply filter panel values to both endpoints.
3. Render read-only monitoring cards/tables.

## 7. Error Handling Map

- `400`: validation/business rule issue
- `401`: invalid/expired token
- `403`: role/ownership denied
- `404`: appointment/session not found
- `409`: state conflict (invalidated/terminal/not-active)
- `502`/`503`: upstream unavailability

Frontend should map these to clear user-facing messages and retry actions where relevant.

## 8. Current Fallback Link Behavior

If Google OAuth is not connected, session provisioning still succeeds using fallback provider links.

Example fallback pattern:

- `https://meet.medstream.local/s/{appointment_id}`

UI should not block on this; show provider label from API response.

## 9. Suggested Frontend State Model

Keep these states separate:

- `appointment_status`
- `telemedicine_session_status`
- `google_integration_status`
- `dashboard_filters`

This avoids mixing consultation outcomes with transport/session lifecycle.

## 10. QA Checklist

- Patient cannot request join link for another patient appointment.
- Doctor cannot request join link for non-owned appointment.
- Admin/staff can request operational join links.
- Technical-failure action persists reason and status.
- Stats include failed sessions and average duration field.
- Live status endpoint respects filters and pagination.
- OAuth connect status transitions from disconnected to connected after consent.
- Fallback link path remains usable when OAuth integration is absent.
