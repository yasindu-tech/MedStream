"""Routers package for appointment-service.

- internal.py  → GET /internal/appointments/booked-slots  (no auth, service-to-service)
- search.py    → GET /doctors/search                       (JWT required, patient-facing)
"""
