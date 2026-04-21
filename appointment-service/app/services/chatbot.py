"""Symptom-to-doctor recommendation service for chatbot MVP."""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Optional
from uuid import UUID

from app.config import settings
from app.schemas import DoctorSearchResult
from app.services import get_doctor_profile, search_doctors

# Keep the taxonomy intentionally transparent for quick iteration.
SPECIALTY_KEYWORDS: dict[str, list[str]] = {
    "Cardiology": [
        "chest pain",
        "palpitations",
        "shortness of breath",
        "heart",
        "high blood pressure",
        "hypertension",
    ],
    "Dermatology": [
        "skin rash",
        "rash",
        "itching",
        "acne",
        "eczema",
        "psoriasis",
    ],
    "Neurology": [
        "migraine",
        "headache",
        "dizziness",
        "numbness",
        "seizure",
        "memory loss",
    ],
    "Obstetrics and Gynecology": [
        "pregnancy",
        "pregnant",
        "period pain",
        "irregular periods",
        "gyne",
        "gynae",
        "pcos",
    ],
    "Orthopedics": [
        "joint pain",
        "knee pain",
        "back pain",
        "fracture",
        "sprain",
    ],
    "ENT": [
        "ear pain",
        "sinus",
        "sore throat",
        "hearing",
        "tonsil",
    ],
    "General Medicine": [
        "fever",
        "cough",
        "cold",
        "fatigue",
        "body pain",
        "infection",
    ],
}

MAX_SPECIALTIES = 3
DEFAULT_CLARIFICATION_QUESTION = (
    "Can you share where the main discomfort is (chest, skin, head, stomach, joints, or pregnancy-related)?"
)


def recommend_doctors_from_symptoms(
    *,
    symptoms: str,
    target_date: Optional[date],
    consultation_type: Optional[str],
    clinic_id: Optional[UUID],
    max_recommendations: int,
) -> dict:
    inferred_specialties, follow_up_question, llm_used = _infer_specialties(symptoms)

    search_plan = inferred_specialties or [None]
    merged = _search_and_merge(
        specialties=search_plan,
        target_date=target_date,
        consultation_type=consultation_type,
        clinic_id=clinic_id,
    )

    ranked = _rank_results(merged, target_date=target_date)
    limited = ranked[: max(1, min(max_recommendations, 10))]

    no_results_guidance = None
    if not limited:
        no_results_guidance = (
            "No doctors matched right now. Try another date or switch consultation type."
        )

    reason = _build_reason(
        inferred_specialties=inferred_specialties,
        follow_up_question=follow_up_question,
        result_count=len(limited),
    )

    return {
        "recommendation_reason": reason,
        "suggested_specialties": inferred_specialties,
        "top_doctors": limited,
        "follow_up_question": follow_up_question,
        "no_results_guidance": no_results_guidance,
        "total": len(limited),
        "empty_state": len(limited) == 0,
        "llm_used": llm_used,
    }


def _normalize_text(text: str) -> str:
    lowered = text.lower().strip()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _rule_based_specialties(symptoms: str) -> list[str]:
    normalized = _normalize_text(symptoms)
    matches: list[tuple[str, int]] = []

    for specialty, keywords in SPECIALTY_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            normalized_keyword = _normalize_text(keyword)
            if normalized_keyword and normalized_keyword in normalized:
                score += 1
        if score > 0:
            matches.append((specialty, score))

    matches.sort(key=lambda item: item[1], reverse=True)
    return [specialty for specialty, _ in matches[:MAX_SPECIALTIES]]


def _infer_specialties(symptoms: str) -> tuple[list[str], Optional[str], bool]:
    llm_specialties: list[str] = []
    llm_used = False

    if settings.chatbot_enable_llm and settings.GEMINI_API_KEY:
        llm_specialties = _infer_with_langchain_gemini(symptoms)
        llm_used = bool(llm_specialties)

    rule_specialties = _rule_based_specialties(symptoms)

    merged: list[str] = []
    for item in llm_specialties + rule_specialties:
        if item and item not in merged:
            merged.append(item)
        if len(merged) >= MAX_SPECIALTIES:
            break

    follow_up_question = None
    if not merged:
        follow_up_question = DEFAULT_CLARIFICATION_QUESTION

    return merged, follow_up_question, llm_used


def _extract_specialties_from_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []

    payload = None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError:
                payload = None

    if not isinstance(payload, dict):
        return []

    values = payload.get("specialties", [])
    if not isinstance(values, list):
        return []

    return [value for value in values if isinstance(value, str) and value in SPECIALTY_KEYWORDS][:MAX_SPECIALTIES]


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        return "\n".join(chunks)
    return ""


def _infer_with_langchain_gemini(symptoms: str) -> list[str]:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        allowed_specialties = sorted(SPECIALTY_KEYWORDS.keys())
        prompt = (
            "You are a medical triage assistant for doctor specialty suggestion. "
            "Return strict JSON only with this shape: "
            '{"specialties": ["..."]}. '
            "Choose only from this allowed specialty list: "
            f"{allowed_specialties}. "
            "If unsure, return an empty specialties array."
            f"\nSymptoms: {symptoms}"
        )

        model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0,
        )
        response = model.invoke(prompt)
        output_text = _content_to_text(getattr(response, "content", ""))

        specialties = _extract_specialties_from_text(output_text)
        if specialties:
            return specialties

        # Non-JSON fallback: pick explicit specialty mentions from allowed list.
        lowered = output_text.lower()
        guessed = [s for s in allowed_specialties if s.lower() in lowered]
        return guessed[:MAX_SPECIALTIES]
    except Exception:
        # Fail open and continue with transparent keyword-based fallback.
        return []


def _search_and_merge(
    *,
    specialties: list[Optional[str]],
    target_date: Optional[date],
    consultation_type: Optional[str],
    clinic_id: Optional[UUID],
) -> list[DoctorSearchResult]:
    merged: dict[tuple[str, str], DoctorSearchResult] = {}

    for specialty in specialties:
        payload = search_doctors(
            specialty=specialty,
            target_date=target_date,
            consultation_type=consultation_type,
            clinic_id=clinic_id,
        )
        for item in payload.get("results", []):
            result = DoctorSearchResult(**item)
            key = (str(result.doctor_id), str(result.clinic_id))
            existing = merged.get(key)
            if existing is None:
                merged[key] = result
                continue
            merged[key] = _pick_better(existing, result)

    return list(merged.values())


def _pick_better(left: DoctorSearchResult, right: DoctorSearchResult) -> DoctorSearchResult:
    if right.has_slots and not left.has_slots:
        return right
    if left.has_slots and not right.has_slots:
        return left

    left_earliest = left.available_slots[0].start_time if left.available_slots else "99:99"
    right_earliest = right.available_slots[0].start_time if right.available_slots else "99:99"
    return right if right_earliest < left_earliest else left


def _rank_results(
    candidates: list[DoctorSearchResult],
    *,
    target_date: Optional[date],
) -> list[DoctorSearchResult]:
    doctor_meta: dict[str, tuple[bool, int]] = {}

    for candidate in candidates:
        doctor_key = str(candidate.doctor_id)
        if doctor_key in doctor_meta:
            continue
        profile_complete = False
        experience_years = -1
        try:
            profile = get_doctor_profile(candidate.doctor_id, target_date=target_date)
            profile_complete = bool(profile.get("profile_complete", False))
            experience_value = profile.get("experience_years")
            if isinstance(experience_value, int):
                experience_years = experience_value
        except Exception:
            # Ranking should still work when profile lookup fails.
            pass
        doctor_meta[doctor_key] = (profile_complete, experience_years)

    def _sort_key(item: DoctorSearchResult) -> tuple[int, str, int, int]:
        profile_complete, experience = doctor_meta.get(str(item.doctor_id), (False, -1))
        earliest = item.available_slots[0].start_time if item.available_slots else "99:99"
        return (
            0 if item.has_slots else 1,
            earliest,
            0 if profile_complete else 1,
            -experience,
        )

    return sorted(candidates, key=_sort_key)


def _build_reason(
    *,
    inferred_specialties: list[str],
    follow_up_question: Optional[str],
    result_count: int,
) -> str:
    if inferred_specialties:
        return (
            "Recommendations are based on symptom-to-specialty matching for: "
            f"{', '.join(inferred_specialties)}. Found {result_count} doctors."
        )
    if follow_up_question:
        return (
            "Your symptoms were ambiguous, so broad recommendations were returned "
            "while requesting one clarification."
        )
    return "Recommendations were generated from broad doctor search filters."
