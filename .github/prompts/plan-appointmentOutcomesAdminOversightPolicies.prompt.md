## Plan: Appointment Outcomes, Admin Oversight, and Policy Configuration

Implement AS-09, AS-10, and AS-11 in appointment-service first (with minimal supporting internal endpoints in clinic-service and telemedicine-service), using existing status history/audit patterns and role middleware. Keep policy behavior dynamic at request time but freeze applied policy on each booking for auditability. Reuse existing roles (`admin`, `staff`) instead of adding new JWT role types.

**Steps**
1. Phase 1 - Authorization and role normalization (blocks most other work) //Keep this as normal because the rola normalization coming as a update from an another dev. So keep that for now and implement other features with the existing roles and then once the role normalization is done we can easily replace the references.
2. In appointment-service, replace references to `clinic_admin` and `system_admin` with current auth roles:
3. `staff` = clinic admin behavior (clinic-scoped)
4. `admin` = system admin behavior (global)
5. Update role guards in routers and role branches in services for cancellation/history/outcome/policy endpoints. *blocks steps 4-10*
6. Add/confirm clinic scoping contract by introducing clinic-service internal endpoint to resolve staff user -> clinic mapping, then consume it via httpx client in appointment-service for staff-scoped queries/actions. *blocks step 6 and part of step 7*

7. Phase 2 - AS-09 appointment outcomes
8. Data model updates in patientcare schema and appointment model:
9. add final outcome timestamps and actor fields (`completed_at`, `completed_by`, `no_show_at`, `no_show_marked_by`) and keep writing to existing appointment_status_history for every transition.
// If we can add a status to add the dr can mark the paitient is arrived
10. Extend valid statuses to include `no_show` and ensure history/filter schemas accept it.
11. Implement outcome service module in appointment-service with transition rules:
12. `confirmed`/`in_progress` -> `completed` allowed for doctor, and admin/staff override allowed before scheduled time
13. reject outcome updates for `cancelled` appointments
14. reject duplicate terminal updates (`completed` or `no_show` already set)
15. timestamp every final outcome update server-side
16. Add public endpoint for doctor marking completion and internal endpoint for system marking no-show (telemedicine trigger path). *parallel with step 7 notification wiring*
17. Telemedicine no-show path: create telemedicine-service internal logic to call appointment-service internal no-show endpoint only after grace period expiry and only if reconnect/join event not observed before deadline.
18. Notification hooks: on completed/no-show, publish notification event payloads through notification-service internal/event endpoint pattern.
19. Trigger follow-up/prescription workflow hooks on completion (stub with clear service boundary if dependent services are not yet implemented).

20. Phase 3 - AS-10 admin oversight
21. Build admin appointment listing endpoint(s) in appointment-service with pagination and filters: patient, doctor, clinic, date range, status.
22. Enforce scope:
23. `staff` users can only query/manage appointments for their own clinic (resolved via clinic-service mapping)
24. `admin` can query platform-wide
25. Complete admin cancellation handlers in cancellation service (existing stubs) and require reason.
26. Add endpoint for appointment status history viewing for admins (reuse existing history response model + broaden filters).
27. Add statistics endpoint for `admin` role showing totals and rates (bookings, cancellations, no-shows), with optional date window and clinic grouping.

28. Phase 4 - AS-11 appointment policies
29. Introduce persistent policy storage in admin DB (global policy + optional clinic override + change history with timestamps).
30. Add policy resolver service in appointment-service:
31. resolve effective policy for each request (latest committed policy)
32. validate cancellation window, reschedule limit, advance booking window, no-show grace period
33. validate all policy inputs as positive/non-zero as appropriate; reject invalid policy writes with 400
34. On booking creation, persist `policy_version_id`/snapshot reference on appointment so existing appointments remain bound to policy active at booking time.
35. Replace hardcoded policy constants usage in cancellation/reschedule and doctor availability logic with resolver calls.
36. Add policy admin APIs (`admin` only): create/update/list effective policies and history.
// Move those appointment resheduling and cancellation policies to database and make them dynamic. So that the admin can change those policies without the need of a code change. Also, we can keep the history of the policy changes in the database with timestamps and the admin user who made the change. This will help us to keep track of the policy changes and also to debug any issues that may arise due to policy changes.

37. Phase 5 - Integration and compatibility hardening
38. Ensure no internal endpoint is exposed through nginx routes.
39. Configure new inter-service URLs in settings/env for appointment-service and telemedicine-service.
40. Apply fail-open/fail-closed behavior explicitly:
41. no-show automation should fail-safe (no automatic terminal status on upstream uncertainty)
42. non-critical notifications should fail-open (log and continue)
43. Ensure history endpoints display final outcomes (`completed`, `no_show`) for doctor/patient/admin views.

44. Phase 6 - Verification and rollout
45. Add/extend tests for transition rules, role scope checks, policy validation, and grace-period no-show behavior.
46. Add integration tests for telemedicine reconnect edge case and admin clinic-bound access denial.
47. Run service-level test scripts and targeted curl checks through gateway/internal routes.
48. Validate query performance for admin list endpoints with pagination on large result sets.

**Relevant files**
- /Users/yasindu/MedStream/appointment-service/app/routers/cancellation.py - role guards and admin cancellation behavior entrypoint
- /Users/yasindu/MedStream/appointment-service/app/services/cancellation.py - existing admin cancel stubs and policy window checks to replace
- /Users/yasindu/MedStream/appointment-service/app/routers/history.py - existing paginated filtering/history endpoint to extend for admin scope
- /Users/yasindu/MedStream/appointment-service/app/services/history.py - scope enforcement and filter/query patterns to reuse
- /Users/yasindu/MedStream/appointment-service/app/models/__init__.py - appointment and status history models (status/timestamp fields)
- /Users/yasindu/MedStream/appointment-service/app/config.py - inter-service URLs and policy defaults/fallbacks
- /Users/yasindu/MedStream/appointment-service/main.py - register new outcome/admin/policy routers
- /Users/yasindu/MedStream/appointment-service/app/routers/internal.py - internal no-show/completion endpoints for system workflows
- /Users/yasindu/MedStream/doctor-service/app/services/doctor_profile.py - replace hardcoded advance booking constant with policy resolver/client
- /Users/yasindu/MedStream/telemedicine-service/app/routers/__init__.py (and new router module) - no-show grace/reconnect detection and callback to appointment-service
- /Users/yasindu/MedStream/notification-service/app/routers/events.py - event contract to reuse for outcome/cancellation notifications
- /Users/yasindu/MedStream/clinic-service/app/routers/internal.py (new or extend) - staff-to-clinic ownership lookup for scoping
- /Users/yasindu/MedStream/infrastructure/db/init-patientcare-db.sql - appointment outcome fields and policy reference columns
- /Users/yasindu/MedStream/infrastructure/db/init-admin-db.sql - policy tables and change-history tables
- /Users/yasindu/MedStream/docker-compose.yml - service env wiring for new policy/URL config

**Verification**
1. Unit tests for AS-09 transition matrix:
2. doctor completion allowed only after scheduled time unless role in (`admin`,`staff`)
3. no-show update rejected for cancelled/completed appointments
4. reconnect during grace period prevents no-show mark
5. status history row inserted for every final-state transition with timestamp and actor
6. Unit/integration tests for AS-10 authorization:
7. staff can list/cancel only own clinic appointments
8. admin can list across clinics and retrieve statistics
9. pagination and filters produce stable deterministic ordering
10. Unit tests for AS-11 policies:
11. reject negative/zero invalid values
12. latest committed policy applies to new requests
13. existing appointment keeps policy snapshot reference from booking time
14. API checks:
15. gateway calls for public endpoints with JWT
16. internal endpoint calls only on Docker network paths (`/internal/*`), not gateway-exposed
17. smoke tests for notification and telemedicine callback paths (including timeout handling)

**Decisions**
- Use existing auth roles: `admin` (system admin behavior) and `staff` (clinic admin behavior)
- Early completion override allowed for both `admin` and `staff`
- Policy changes affect new bookings only; existing bookings remain bound to booking-time policy reference
- Internal endpoints remain non-JWT and not exposed in nginx

**Further Considerations**
1. Clarify whether `staff` users can mark `no_show` directly from UI or only through telemedicine/system automation; recommended: allow both with audit reason.
2. Decide if stats endpoint needs cached aggregates for large data volumes; recommended: start with query-time aggregate + date window, add materialized view only if needed.
3. Decide whether to expose policy history in appointment-service only or also mirror read-only in clinic-service; recommended: keep source-of-truth in appointment-service/admin DB and expose one read API.