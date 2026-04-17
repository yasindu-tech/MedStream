## Plan: Symptom-to-Doctor Chatbot MVP

Build a simple rule-based chatbot flow that converts patient symptom text into specialty filters, reuses existing appointment-service doctor search/profile APIs, and returns ranked doctor recommendations in a chat-like response format.

We have to use an LLM for this, but we want to keep it as simple as possible for the MVP. The main goal is to validate the end-to-end flow of symptom input → specialty inference → doctor recommendation without getting bogged down in complex NLP or conversational state management.

Use an framework like langchain to structure the symptom parsing and doctor search orchestration logic, but keep the actual symptom-to-specialty mapping rules simple and transparent (e.g. keyword-based with some normalization). This will allow us to iterate quickly on the rules based on real user input without needing to retrain models or manage complex state.
**Steps**
1. Phase 1 - Discovery and symptom taxonomy definition (blocks all later phases)
2. Define MVP symptom categories and map each category to one or more existing doctor specializations used by doctor-service search.
3. Add a fallback path for unknown symptom text: ask one clarification question and then default to broad search.
4. Phase 2 - Chatbot API design in appointment-service (depends on phase 1)
5. Add a new public endpoint for chatbot recommendations in appointment-service that accepts symptom text and optional filters (date, consultation_type, clinic_id).
6. Keep endpoint stateless for MVP (single-turn request/response) to avoid session persistence complexity.
7. Define response contract with recommendation_reason, suggested_specialties, top_doctors, and follow_up_question.
8. Phase 3 - Chatbot service logic (depends on phase 2)
9. Implement symptom parser module (keyword/rule matching with lightweight normalization) to infer specialty candidates.
10. Reuse existing search_doctors call path in appointment-service services layer to fetch doctor candidates.
11. If multiple specialties are inferred, run merged searches and rank by: has_slots first, earliest available slot, then profile completeness/experience where available.
12. Include no-results guidance in response (alternate specialty suggestion or date/consultation_type relaxation hint).
13. Phase 4 - Router wiring and gateway compatibility (depends on phases 2-3)
14. Register new chatbot router under appointment-service public routes so it remains gateway-exposed through /appointments/*.
15. Keep internal-only endpoints unchanged and do not expose new /internal paths via gateway.
16. Phase 5 - Frontend integration contract (parallel after phase 2)
17. Provide a minimal chat interaction sequence for frontend: user symptom input, bot clarification (if needed), recommendation cards, and optional handoff to existing booking flow.
18. Use existing booking endpoint payload fields when user selects a doctor and slot.
19. Phase 6 - Verification (depends on phases 3-5)
20. Validate specialty extraction accuracy on a symptom sample set (happy-path plus ambiguous symptoms).
21. Validate recommendation endpoint returns consistent results for the same inputs and returns 200 with empty list guidance when no matches.
22. Validate downstream booking handoff fields align with existing BookAppointmentRequest schema.

**Relevant files**
- /Users/yasindu/MedStream/appointment-service/app/routers/search.py — reuse existing doctor search interface and patterns.
- /Users/yasindu/MedStream/appointment-service/app/schemas/__init__.py — mirror response style and create chatbot request/response models.
- /Users/yasindu/MedStream/appointment-service/app/services/__init__.py — add chatbot recommendation orchestration helpers or import wiring.
- /Users/yasindu/MedStream/doctor-service/app/services/doctor_search.py — existing specialization/date/consultation filtering and slot-based sorting to reuse.
- /Users/yasindu/MedStream/appointment-service/main.py — ensure chatbot router registration if split into a new router file.
- /Users/yasindu/MedStream/api-gateway/nginx.conf — no route changes expected if endpoint stays under /appointments/*; verify only.

**Verification**
1. API-level: POST chatbot endpoint with symptoms like chest pain, skin rash, migraine, and pregnancy follow-up; verify expected specialty mapping.
2. Integration-level: confirm endpoint internally calls existing doctor search path and returns doctors with available_slots and has_slots fields.
3. Edge cases: unknown symptom text, multiple symptoms across specialties, no matching doctors, and invalid date/consultation_type input.
4. Frontend contract: confirm response includes enough fields to render simple doctor cards and trigger booking payload creation.

**Decisions**
- MVP approach: rule-based symptom extraction, not LLM-dependent.
- Scope: recommend doctors and provide booking handoff data; full conversational memory is out of scope.
- Reuse-first: no new doctor ranking engine or new service required for MVP; leverage existing appointment/doctor search primitives.

**Further Considerations**
1. Add lightweight analytics on symptom-to-specialty mapping misses to improve keyword rules safely over time.
2. Introduce multilingual symptom synonyms later (English/Sinhala/Tamil) after MVP stabilization.
3. If recommendation quality is insufficient, phase-2 upgrade can add an LLM classifier behind the same endpoint contract.