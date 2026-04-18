from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx

from app.config import settings
from app.services.appointment_client import get_pre_consultation_context
from app.services.patient_client import get_patient_medical_summary


def generate_doctor_patient_overview(*, appointment_id: UUID, doctor_user_id: str) -> dict[str, Any]:
    appt_context = get_pre_consultation_context(
        appointment_id=appointment_id,
        doctor_user_id=doctor_user_id,
    )
    patient_id = UUID(str(appt_context["patient"]["patient_id"]))
    patient_summary = get_patient_medical_summary(patient_id=patient_id)

    allergies = patient_summary.get("allergies", [])
    chronic_conditions = patient_summary.get("chronic_conditions", [])
    prescriptions = patient_summary.get("prescriptions", [])
    consultation_notes = appt_context.get("recent_notes", [])
    clinics = appt_context.get("clinic_history", [])
    reports = patient_summary.get("documents", [])

    report_insights = _extract_report_insights(reports)
    overall_summary, llm_used = _build_overall_summary(
        patient=patient_summary.get("profile", {}),
        allergies=allergies,
        chronic_conditions=chronic_conditions,
        prescriptions=prescriptions,
        consultation_notes=consultation_notes,
        report_insights=report_insights,
    )

    sections = [
        _patient_snapshot_section(patient_summary.get("profile", {}), appt_context.get("appointment", {})),
        _allergy_section(allergies),
        _condition_section(chronic_conditions),
        _medication_section(prescriptions),
        _notes_section(consultation_notes),
        _clinic_history_section(clinics),
        _report_section(report_insights, reports),
    ]

    risk_flags = _build_risk_flags(allergies, chronic_conditions, report_insights)
    focus_areas = _build_focus_areas(allergies, chronic_conditions, prescriptions, report_insights)

    return {
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "llm_used": llm_used,
        "overall_summary": overall_summary,
        "risk_flags": risk_flags,
        "suggested_focus_areas": focus_areas,
        "sections": sections,
    }


def _patient_snapshot_section(patient: dict[str, Any], appointment: dict[str, Any]) -> dict[str, Any]:
    highlights = [
        f"Patient: {patient.get('full_name', 'Unknown')}",
        f"DOB: {patient.get('dob') or 'Not provided'}",
        f"Gender: {patient.get('gender') or 'Not provided'}",
        f"Blood group: {patient.get('blood_group') or 'Not provided'}",
        f"Appointment: {appointment.get('appointment_date')} {appointment.get('start_time')} - {appointment.get('end_time')}",
    ]
    return {
        "key": "patient_snapshot",
        "title": "Patient Snapshot",
        "summary": "Demographics and current appointment context prepared for quick consultation start.",
        "highlights": highlights,
        "source_count": 1,
        "latest_source_at": appointment.get("appointment_date"),
    }


def _allergy_section(allergies: list[dict[str, Any]]) -> dict[str, Any]:
    highlights = []
    for allergy in allergies[:8]:
        name = str(allergy.get("allergy_name") or "Unnamed allergy")
        note = allergy.get("note")
        line = f"Allergy: {name}"
        if note:
            line = f"{line} | Clinical note: {str(note).strip()}"
        highlights.append(line)

    if not highlights:
        highlights = ["No allergies recorded in patient profile."]

    return {
        "key": "allergies",
        "title": "Allergy Alerts",
        "summary": "Allergy records that should be checked before prescribing or administering treatment.",
        "highlights": highlights,
        "source_count": len(allergies),
        "latest_source_at": None,
    }


def _condition_section(conditions: list[dict[str, Any]]) -> dict[str, Any]:
    highlights = []
    for condition in conditions[:8]:
        name = str(condition.get("condition_name") or "Unnamed condition")
        note = condition.get("note")
        line = f"Condition: {name}"
        if note:
            line = f"{line} | Clinical note: {str(note).strip()}"
        highlights.append(line)

    if not highlights:
        highlights = ["No chronic conditions recorded."]

    return {
        "key": "chronic_conditions",
        "title": "Chronic Conditions",
        "summary": "Known chronic diseases and long-term health background relevant to diagnosis.",
        "highlights": highlights,
        "source_count": len(conditions),
        "latest_source_at": None,
    }


def _medication_section(prescriptions: list[dict[str, Any]]) -> dict[str, Any]:
    highlights = []
    latest_source_at = None
    for prescription in prescriptions[:8]:
        meds = prescription.get("medications") if isinstance(prescription.get("medications"), list) else []
        med_lines: list[str] = []
        for med in meds[:4]:
            if not isinstance(med, dict):
                continue
            name = str(med.get("name") or "Unnamed medication")
            dosage = med.get("dosage")
            frequency = med.get("frequency")
            duration = med.get("duration")
            med_parts = [name]
            if dosage:
                med_parts.append(f"dosage={dosage}")
            if frequency:
                med_parts.append(f"frequency={frequency}")
            if duration:
                med_parts.append(f"duration={duration}")
            if len(med_parts) > 1:
                med_lines.append(f"{med_parts[0]} ({', '.join(med_parts[1:])})")
            else:
                med_lines.append(med_parts[0])

        created_at = prescription.get("created_at") or "unknown date"
        status = prescription.get("status") or "unknown"
        instructions = (prescription.get("instructions") or "").strip()
        instruction_suffix = f" | Instructions: {instructions}" if instructions else ""
        if med_lines:
            highlights.append(
                f"{created_at} | status={status} | Medications: {'; '.join(med_lines)}{instruction_suffix}"
            )
        else:
            highlights.append(f"{created_at} | status={status} | Medication details unavailable{instruction_suffix}")
        if latest_source_at is None:
            latest_source_at = prescription.get("created_at")

    if not highlights:
        highlights = ["No prescription history found."]

    return {
        "key": "prescriptions",
        "title": "Prescription Timeline",
        "summary": "Recent prescribed medications and treatment history.",
        "highlights": highlights,
        "source_count": len(prescriptions),
        "latest_source_at": latest_source_at,
    }


def _notes_section(notes: list[dict[str, Any]]) -> dict[str, Any]:
    highlights = []
    latest_source_at = None
    for note in notes[:8]:
        content = (note.get("content") or "").strip()
        short = content[:220] + ("..." if len(content) > 220 else "")
        highlights.append(short or "Empty note entry")
        if latest_source_at is None:
            latest_source_at = note.get("created_at")

    if not highlights:
        highlights = ["No previous consultation notes found."]

    return {
        "key": "consultation_notes",
        "title": "Previous Consultation Notes",
        "summary": "Clinical notes from previous appointments for continuity of care.",
        "highlights": highlights,
        "source_count": len(notes),
        "latest_source_at": latest_source_at,
    }


def _clinic_history_section(clinics: list[dict[str, Any]]) -> dict[str, Any]:
    highlights = []
    latest_source_at = None
    for clinic in clinics[:8]:
        name = clinic.get("clinic_name") or "Unknown clinic"
        count = clinic.get("visit_count", 0)
        last_visit = clinic.get("last_visit_date")
        highlights.append(f"{name}: {count} visit(s), last visit {last_visit or 'unknown'}")
        if latest_source_at is None:
            latest_source_at = last_visit

    if not highlights:
        highlights = ["No clinic visit history available."]

    return {
        "key": "clinic_history",
        "title": "Clinic Visit History",
        "summary": "Recent clinic interactions and attendance pattern.",
        "highlights": highlights,
        "source_count": len(clinics),
        "latest_source_at": latest_source_at,
    }


def _extract_report_insights(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    for report in reports[:6]:
        file_name = report.get("file_name") or "unknown"
        document_type = report.get("document_type") or "unknown"
        uploaded_at = report.get("uploaded_at")
        url = report.get("file_url")
        if not isinstance(url, str) or not url:
            insights.append(
                {
                    "file_name": file_name,
                    "document_type": document_type,
                    "uploaded_at": uploaded_at,
                    "summary": "Report URL not available. Unable to extract report content.",
                }
            )
            continue

        extracted_text = _fetch_report_text(url)
        if extracted_text:
            snippet = extracted_text[: settings.REPORT_TEXT_MAX_CHARS]
            insights.append(
                {
                    "file_name": file_name,
                    "document_type": document_type,
                    "uploaded_at": uploaded_at,
                    "summary": snippet,
                }
            )
        else:
            insights.append(
                {
                    "file_name": file_name,
                    "document_type": document_type,
                    "uploaded_at": uploaded_at,
                    "summary": "Could not extract report text. Metadata retained for doctor review.",
                }
            )
    return insights


def _fetch_report_text(url: str) -> str | None:
    try:
        with httpx.Client(timeout=settings.REPORT_FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = (response.headers.get("content-type") or "").lower()
            if "text" in content_type or "json" in content_type or "xml" in content_type:
                text = response.text.strip()
                return text if text else None
            return None
    except Exception:
        return None


def _report_section(report_insights: list[dict[str, Any]], reports: list[dict[str, Any]]) -> dict[str, Any]:
    highlights = []
    latest_source_at = None
    for insight in report_insights[:6]:
        summary = insight.get("summary", "")
        short = summary[:260] + ("..." if len(summary) > 260 else "")
        file_name = insight.get("file_name", "report")
        document_type = insight.get("document_type") or "unknown"
        uploaded_at = insight.get("uploaded_at") or "unknown"
        highlights.append(f"{file_name} | type={document_type} | uploaded={uploaded_at} | Findings: {short}")
        if latest_source_at is None and insight.get("uploaded_at"):
            latest_source_at = insight.get("uploaded_at")

    if reports and not latest_source_at:
        latest_source_at = reports[0].get("uploaded_at")

    if not highlights:
        highlights = ["No reports/documents were found for this patient."]

    return {
        "key": "reports",
        "title": "Reports and Documents",
        "summary": "Report/document content and metadata summary for pre-consultation review.",
        "highlights": highlights,
        "source_count": len(reports),
        "latest_source_at": latest_source_at,
    }


def _build_risk_flags(
    allergies: list[dict[str, Any]],
    chronic_conditions: list[dict[str, Any]],
    report_insights: list[dict[str, Any]],
) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []

    if allergies:
        flags.append(
            {
                "severity": "high",
                "title": "Allergy verification required",
                "reason": f"{len(allergies)} allergy record(s) found; verify before prescribing or procedures.",
            }
        )

    if chronic_conditions:
        flags.append(
            {
                "severity": "medium",
                "title": "Chronic condition review required",
                "reason": f"{len(chronic_conditions)} chronic condition(s) recorded; align treatment plan accordingly.",
            }
        )

    unresolved_reports = sum(1 for item in report_insights if "Could not extract" in item.get("summary", ""))
    if unresolved_reports:
        flags.append(
            {
                "severity": "medium",
                "title": "Manual report review advised",
                "reason": f"{unresolved_reports} report(s) could not be text-extracted and need manual review.",
            }
        )

    if not flags:
        flags.append(
            {
                "severity": "low",
                "title": "No immediate risk flags",
                "reason": "No major risk indicators were detected in available records.",
            }
        )

    return flags


def _build_focus_areas(
    allergies: list[dict[str, Any]],
    chronic_conditions: list[dict[str, Any]],
    prescriptions: list[dict[str, Any]],
    report_insights: list[dict[str, Any]],
) -> list[str]:
    focus: list[str] = ["Confirm current chief complaint and symptom timeline."]

    if allergies:
        focus.append("Reconfirm allergy list and potential medication contraindications.")
    if chronic_conditions:
        focus.append("Assess chronic condition control and treatment adherence.")
    if prescriptions:
        focus.append("Review recent medication response and adverse effects.")
    if report_insights:
        focus.append("Cross-check latest report findings with physical examination.")

    return focus[:5]


def _build_overall_summary(
    *,
    patient: dict[str, Any],
    allergies: list[dict[str, Any]],
    chronic_conditions: list[dict[str, Any]],
    prescriptions: list[dict[str, Any]],
    consultation_notes: list[dict[str, Any]],
    report_insights: list[dict[str, Any]],
) -> tuple[str, bool]:
    allergy_count = len(allergies)
    condition_count = len(chronic_conditions)
    prescription_count = len(prescriptions)
    note_count = len(consultation_notes)

    allergy_detail = ", ".join(
        [
            f"{item.get('allergy_name', 'Unnamed allergy')} ({item.get('note', 'no note')})"
            for item in allergies[:4]
        ]
    ) or "No allergies recorded"
    condition_detail = ", ".join(
        [
            f"{item.get('condition_name', 'Unnamed condition')} ({item.get('note', 'no note')})"
            for item in chronic_conditions[:4]
        ]
    ) or "No chronic conditions recorded"
    prescription_detail = ", ".join(_summarize_prescription_for_prompt(item) for item in prescriptions[:4]) or "No prescriptions recorded"
    report_detail = ", ".join(
        [
            f"{item.get('file_name', 'report')} => {str(item.get('summary', 'no summary'))[:120]}"
            for item in report_insights[:4]
        ]
    ) or "No reports/documents recorded"

    base_summary = (
        f"{patient.get('full_name', 'Patient')} has {allergy_count} recorded allergy(ies), "
        f"{condition_count} chronic condition(s), {prescription_count} prescription record(s), "
        f"{note_count} prior consultation note(s), and {len(report_insights)} report/document entry(ies). "
        f"Allergies: {allergy_detail}. Chronic conditions: {condition_detail}. "
        f"Prescriptions: {prescription_detail}. Reports: {report_detail}."
    )

    if not (settings.chatbot_enable_llm and settings.GEMINI_API_KEY):
        return base_summary, False

    llm_summary = _summarize_with_gemini(
        patient=patient,
        allergies=allergies,
        chronic_conditions=chronic_conditions,
        prescriptions=prescriptions,
        consultation_notes=consultation_notes,
        report_insights=report_insights,
        fallback_summary=base_summary,
    )
    if llm_summary:
        return llm_summary, True
    return base_summary, False


def _summarize_prescription_for_prompt(prescription: dict[str, Any]) -> str:
    created_at = prescription.get("created_at") or "unknown date"
    status = prescription.get("status") or "unknown"
    meds = prescription.get("medications") if isinstance(prescription.get("medications"), list) else []
    med_names = [str(med.get("name")) for med in meds[:3] if isinstance(med, dict) and med.get("name")]
    if not med_names:
        med_names = ["medication details unavailable"]
    return f"{created_at} status={status}: {', '.join(med_names)}"


def _summarize_with_gemini(
    *,
    patient: dict[str, Any],
    allergies: list[dict[str, Any]],
    chronic_conditions: list[dict[str, Any]],
    prescriptions: list[dict[str, Any]],
    consultation_notes: list[dict[str, Any]],
    report_insights: list[dict[str, Any]],
    fallback_summary: str,
) -> str | None:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        allergy_lines = [
            f"- {item.get('allergy_name', 'Unnamed allergy')}: {item.get('note', 'No note')}"
            for item in allergies[:8]
        ] or ["- None recorded"]
        condition_lines = [
            f"- {item.get('condition_name', 'Unnamed condition')}: {item.get('note', 'No note')}"
            for item in chronic_conditions[:8]
        ] or ["- None recorded"]
        prescription_lines = [
            f"- {_summarize_prescription_for_prompt(item)}"
            for item in prescriptions[:8]
        ] or ["- None recorded"]
        note_lines = [
            f"- {(item.get('content') or 'Empty note')[:220]}"
            for item in consultation_notes[:6]
        ] or ["- None recorded"]
        report_lines = [
            f"- {item.get('file_name', 'report')} ({item.get('document_type', 'unknown')}): {str(item.get('summary', 'No summary'))[:260]}"
            for item in report_insights[:6]
        ] or ["- None recorded"]

        prompt = f"""
You are a senior clinical assistant writing a pre-consultation briefing for a doctor.

Goal:
- Articulate the patient's key risks and history with as much useful detail as available.
- Explicitly mention what allergies exist, what chronic diseases exist, what prescriptions are active/recent, and what reports suggest.
- If a category has no records, clearly state no data is available.

Style requirements:
- Plain text only, no markdown.
- 6 to 8 concise but information-dense clinical sentences.
- Neutral, factual, and safety-focused tone.
- Avoid generic statements when specific details are available.

Patient profile:
- Name: {patient.get('full_name', 'Unknown')}
- DOB: {patient.get('dob') or 'Not provided'}
- Gender: {patient.get('gender') or 'Not provided'}
- Blood group: {patient.get('blood_group') or 'Not provided'}

Allergies:
{chr(10).join(allergy_lines)}

Chronic conditions:
{chr(10).join(condition_lines)}

Prescriptions:
{chr(10).join(prescription_lines)}

Consultation notes:
{chr(10).join(note_lines)}

Reports and findings:
{chr(10).join(report_lines)}

Fallback baseline summary:
{fallback_summary}
""".strip()

        model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0,
        )
        response = model.invoke(prompt)
        content = getattr(response, "content", "")
        if isinstance(content, str):
            text = content.strip()
            return text or None
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, str):
                    chunks.append(item)
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    chunks.append(item["text"])
            merged = "\n".join(chunks).strip()
            return merged or None
        return None
    except Exception:
        return None
