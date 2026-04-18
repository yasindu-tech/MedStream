from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any
from uuid import UUID

from app.config import settings
from app.services.appointment_client import get_post_consultation_context


def generate_post_consultation_summary(*, appointment_id: UUID) -> dict[str, Any]:
    context = get_post_consultation_context(appointment_id=appointment_id)
    appointment = context.get("appointment", {})
    patient = context.get("patient", {})
    note = context.get("consultation_note", {})
    prescription = context.get("prescription", {})
    follow_up = context.get("follow_up", {})

    patient_email = _normalize_text(patient.get("email"))
    diagnosis = _normalize_text(note.get("diagnosis"))
    symptoms = _normalize_text(note.get("symptoms"))
    advice = _normalize_text(note.get("advice"))
    prescription_instructions = _normalize_text(prescription.get("instructions"))
    follow_up_advice = _build_follow_up_advice(follow_up)
    medications = _normalize_medications(prescription.get("medications"))

    missing_fields = []
    if not diagnosis:
        missing_fields.append("diagnosis")
    if not advice and not symptoms:
        missing_fields.append("consultation_notes")

    warnings: list[str] = []
    if not patient_email:
        warnings.append("patient_email_missing")

    generated_at = datetime.now(timezone.utc).isoformat()
    common_payload = {
        "appointment_id": appointment_id,
        "patient_id": UUID(str(patient.get("patient_id"))),
        "patient_user_id": patient.get("user_id"),
        "patient_email": patient_email,
        "patient_name": str(patient.get("full_name") or "Patient"),
        "doctor_name": appointment.get("doctor_name"),
        "generated_at": generated_at,
        "email_eligible": bool(patient_email),
        "missing_fields": missing_fields,
        "diagnosis": diagnosis,
        "medications": medications,
        "warnings": warnings,
    }

    if missing_fields:
        return {
            **common_payload,
            "status": "skipped",
            "llm_used": False,
            "sections": [],
            "summary_text": "",
            "summary_html": "",
        }

    section_map = _build_section_map(
        diagnosis=diagnosis,
        medications=medications,
        symptoms=symptoms,
        advice=advice,
        prescription_instructions=prescription_instructions,
        follow_up_advice=follow_up_advice,
    )

    fallback_text = _build_fallback_summary_text(
        patient_name=common_payload["patient_name"],
        doctor_name=appointment.get("doctor_name"),
        section_map=section_map,
    )

    llm_text = None
    llm_used = False
    if settings.post_consultation_enable_llm and settings.GEMINI_API_KEY:
        llm_text = _generate_with_gemini(
            patient_name=common_payload["patient_name"],
            doctor_name=appointment.get("doctor_name"),
            section_map=section_map,
        )
        llm_used = bool(llm_text)

    summary_text = _review_summary_text(llm_text or fallback_text, section_map)
    summary_html = _build_summary_html(
        patient_name=common_payload["patient_name"],
        appointment=appointment,
        section_map=section_map,
        summary_text=summary_text,
    )
    status = "generated" if llm_used else "fallback"

    return {
        **common_payload,
        "status": status,
        "llm_used": llm_used,
        "sections": [
            {"key": key, "title": title, "content": content}
            for key, title, content in _section_tuples(section_map)
        ],
        "summary_text": summary_text,
        "summary_html": summary_html,
    }


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > settings.POST_CONSULTATION_MAX_NOTES_CHARS:
        return text[: settings.POST_CONSULTATION_MAX_NOTES_CHARS].strip()
    return text


def _normalize_medications(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = _normalize_text(item.get("name")) or "Medication"
        normalized.append(
            {
                "name": name,
                "dosage": _normalize_text(item.get("dosage")) or None,
                "frequency": _normalize_text(item.get("frequency")) or None,
                "duration": _normalize_text(item.get("duration")) or None,
                "notes": _normalize_text(item.get("notes")) or None,
            }
        )
    return normalized


def _build_follow_up_advice(follow_up: dict[str, Any]) -> str:
    if not isinstance(follow_up, dict) or not follow_up:
        return ""
    followup_date = _normalize_text(follow_up.get("suggested_date"))
    followup_time = _normalize_text(follow_up.get("suggested_start_time"))
    followup_note = _normalize_text(follow_up.get("notes"))
    if followup_date and followup_time:
        base = f"Recommended follow-up on {followup_date} at {followup_time}."
    elif followup_date:
        base = f"Recommended follow-up on {followup_date}."
    else:
        base = ""
    if followup_note:
        return f"{base} {followup_note}".strip()
    return base


def _build_section_map(
    *,
    diagnosis: str,
    medications: list[dict[str, Any]],
    symptoms: str,
    advice: str,
    prescription_instructions: str,
    follow_up_advice: str,
) -> dict[str, dict[str, str]]:
    section_map: dict[str, dict[str, str]] = {
        "diagnosis": {
            "title": "Diagnosis",
            "content": diagnosis,
        },
        "care_instructions": {
            "title": "Care Instructions",
            "content": advice,
        },
        "doctor_notes": {
            "title": "Doctor Notes",
            "content": symptoms or "No additional symptom notes were recorded.",
        },
        "follow_up_advice": {
            "title": "Follow-up Advice",
            "content": follow_up_advice or "Follow your doctor's guidance on when to schedule your next consultation.",
        },
    }
    if prescription_instructions:
        section_map["care_instructions"]["content"] = f"{advice}\n\nPrescription note: {prescription_instructions}".strip()
    if medications:
        section_map["medicines"] = {
            "title": "Prescribed Medicines",
            "content": _render_medications(medications),
        }
    return section_map


def _render_medications(medications: list[dict[str, Any]]) -> str:
    lines = []
    for item in medications:
        parts = [item["name"]]
        if item.get("dosage"):
            parts.append(f"dosage {item['dosage']}")
        if item.get("frequency"):
            parts.append(f"take {item['frequency']}")
        if item.get("duration"):
            parts.append(f"for {item['duration']}")
        if item.get("notes"):
            parts.append(item["notes"])
        lines.append(", ".join(parts))
    return "\n".join(lines)


def _build_fallback_summary_text(
    *,
    patient_name: str,
    doctor_name: Any,
    section_map: dict[str, dict[str, str]],
) -> str:
    doctor_fragment = f" by Dr. {doctor_name}" if doctor_name else ""
    body = [f"Hello {patient_name}, here is your post-consultation care summary{doctor_fragment}."]
    for key, title, content in _section_tuples(section_map):
        body.append(f"{title}: {content}")
    body.append("If symptoms worsen or you notice side effects, contact your care team promptly.")
    return "\n\n".join(body)


def _generate_with_gemini(*, patient_name: str, doctor_name: Any, section_map: dict[str, dict[str, str]]) -> str | None:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        lines = [f"- {title}: {content}" for _, title, content in _section_tuples(section_map)]
        doctor_text = str(doctor_name) if doctor_name else "your doctor"
        prompt = f"""
You are generating a patient-friendly follow-up summary after a consultation.

Rules:
- Plain text only, no markdown.
- Keep the tone clear, supportive, and simple.
- Include diagnosis, medicines (if provided), care instructions, and follow-up advice.
- Do not invent medications, dosages, or diagnoses.
- Keep to 6 to 10 short paragraphs.

Patient name: {patient_name}
Doctor: {doctor_text}

Source details:
{chr(10).join(lines)}
""".strip()

        model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0,
        )
        response = model.invoke(prompt)
        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content.strip() or None
        if isinstance(content, list):
            chunks = []
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


def _review_summary_text(candidate_text: str, section_map: dict[str, dict[str, str]]) -> str:
    normalized = candidate_text.strip()
    if not normalized:
        normalized = "Your consultation summary is available."

    lowered = normalized.lower()
    required_phrases = {
        "diagnosis": "diagnosis",
        "care_instructions": "care instructions",
        "follow_up_advice": "follow-up",
    }
    appendixes: list[str] = []
    for key, marker in required_phrases.items():
        if marker not in lowered and key in section_map:
            appendixes.append(f"{section_map[key]['title']}: {section_map[key]['content']}")
    if "medicines" in section_map and "medicine" not in lowered and "medication" not in lowered:
        appendixes.append(f"{section_map['medicines']['title']}: {section_map['medicines']['content']}")
    if appendixes:
        normalized = f"{normalized}\n\n" + "\n\n".join(appendixes)

    return normalized


def _build_summary_html(
    *,
    patient_name: str,
    appointment: dict[str, Any],
    section_map: dict[str, dict[str, str]],
    summary_text: str,
) -> str:
    date_label = escape(str(appointment.get("appointment_date") or ""))
    doctor = escape(str(appointment.get("doctor_name") or "Doctor"))
    clinic = escape(str(appointment.get("clinic_name") or "MedStream"))

    section_html = []
    for _, title, content in _section_tuples(section_map):
        lines = "<br/>".join(escape(line) for line in content.splitlines()) if content else ""
        section_html.append(
            f"<h3 style='margin:18px 0 8px;color:#0F172A;font-size:16px;'>{escape(title)}</h3>"
            f"<p style='margin:0;color:#334155;line-height:1.65;font-size:14px;'>{lines}</p>"
        )
    body = "".join(section_html)
    preview = "<br/>".join(escape(line) for line in summary_text.splitlines()[:2])

    return f"""
<html>
  <body style="margin:0;padding:0;background:#F8FAFC;font-family:Arial,Helvetica,sans-serif;">
    <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="padding:24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" cellpadding="0" cellspacing="0" width="100%" style="max-width:660px;background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;overflow:hidden;">
            <tr>
              <td style="padding:22px 24px;background:linear-gradient(135deg,#0B4F6C,#0EA5E9);color:#fff;">
                <div style="font-size:12px;letter-spacing:.06em;text-transform:uppercase;opacity:.9;">MedStream</div>
                <div style="font-size:22px;font-weight:700;margin-top:6px;">Post-Consultation Care Summary</div>
              </td>
            </tr>
            <tr>
              <td style="padding:24px;">
                <p style="margin:0 0 10px;color:#0F172A;font-size:15px;line-height:1.6;">Hello {escape(patient_name)},</p>
                <p style="margin:0;color:#475569;font-size:14px;line-height:1.6;">This summary was prepared after your consultation on {date_label} with {doctor} at {clinic}.</p>
                <p style="margin:14px 0 0;color:#334155;font-size:14px;line-height:1.6;">{preview}</p>
                {body}
                <p style="margin:18px 0 0;color:#64748B;font-size:12px;line-height:1.6;">This summary is for guidance and does not replace urgent medical care.</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".strip()


def _section_tuples(section_map: dict[str, dict[str, str]]) -> list[tuple[str, str, str]]:
    order = ["diagnosis", "medicines", "care_instructions", "doctor_notes", "follow_up_advice"]
    output: list[tuple[str, str, str]] = []
    for key in order:
        section = section_map.get(key)
        if not section:
            continue
        output.append((key, section["title"], section["content"]))
    return output
