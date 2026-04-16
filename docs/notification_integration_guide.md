# MedStream Notification Service Integration Guide

The `notification-service` is an asynchronous, event-driven internal service running on port `8007`. It manages **In-App WebSockets**, **Emails**, and **SMS routing** centrally so that other microservices do not need to implement their own mailing logic. 

Whenever an event occurs inside your microservice (e.g. an appointment is booked or cancelled), you simply fire a `POST` request to the Notification Service's `/events` endpoint, and it handles queueing, rendering templates, and dispatching.

---

## 1. Emitting Notifications from Backend Services

### Endpoint 
`POST http://notification-service:8007/api/notifications/events`

> [!NOTE]
> This is a strictly internal endpoint routed behind our API gateway. You **do not** need to attach a JWT `Authorization` header to this request.

### The JSON Payload (`EventCreate`)

You must construct an event JSON encapsulating the data payload precisely matching what the Notification Template expects.

| Field | Type | Description |
|---|---|---|
| `event_type` | string | Used to resolve the exact template (e.g., `"appointment.booked"`, `"appointment.cancelled"`). |
| `user_id` | UUID | The Auth ID of the user receiving the notification. |
| `payload` | dict | Key-Value pairs that will be injected into the template variables securely. |
| `channels` | array | Methods of delivery. Valid options: `["in_app", "email", "sms"]`. |
| `priority` | string | Standard options: `"high"`, `"normal"`, `"low"`. defaults to `"normal"`. |

### Example Python Integration (e.g., inside `appointment-service/app/services/booking.py`)

Using the asynchronous `httpx` or synchronous `requests` library:

```python
import httpx
import logging

def notify_appointment_booked(appointment, patient_auth_id: str, doctor_name: str):
    payload = {
        "event_type": "appointment.booked",
        "user_id": patient_auth_id,
        "payload": {
            "patient_name": "John Doe",  # Resolve actual name dynamically
            "doctor_name": doctor_name,
            "date": str(appointment.appointment_date),
            "time": str(appointment.start_time),
            "appointment_id": str(appointment.appointment_id)
        },
        "channels": ["in_app", "email"],
        "priority": "high"
    }

    try:
        # We fire and forget. The notification-service handles retries and queuing natively via the database!
        httpx.post("http://notification-service:8007/api/notifications/events", json=payload, timeout=5.0)
    except Exception as e:
        logging.error(f"Failed to push notification webhook: {e}")
```

---

## 2. Notification Pipeline & Templates

When `notification-service` receives the `/events` POST request:
1. It validates the request format natively via `EventCreate` schema.
2. It looks up the DB `notification_templates` dynamically matching the injected `event_type` parameter.
3. If no matching template exists, or duplicate keys resolve quickly, it returns functionally cleanly without crashing your caller.
4. It places standard requests directly inside the `notification_queue` database explicitly immediately returning HTTP 200 `{"status": "queued"}`.

### Background Queue Worker
Inside `notification-service/main.py`, a background asyncio thread `process_notification_queue()` processes the queues precisely handling templates parsing strings dynamically:

*Example Template stored internally:*
*"Hello {{ patient_name }}, your appointment with {{ doctor_name }} is confirmed for {{ date }} at {{ time }}."*

> [!TIP]
> **Extending Events Contextually:** Whenever creating a new feature requiring a specific email—like "AS-05 Reschedule"—ensure `notification-service` seeds a new template `event_type='appointment.rescheduled'` handling `old_start_time` mapping natively against what your microservice intends to drop into the `payload`!

---

## 3. Frontend Implementation Context

For the frontend engineering team fetching these specific pushes:

1. **REST Inbox**: `GET /inbox/{user_id}?page=1&size=20` (Returns all persistent historically preserved in_app messages mapped against this user)
2. **Real-time WebSockets**: `ws://localhost:8080/notifications/ws/{user_id}` (Pushes JSON data locally enabling immediate UI toaster popups entirely dynamically without requiring the browser to ping servers endlessly!)
