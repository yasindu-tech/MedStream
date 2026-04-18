from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.schemas.notification import ContactUsRequest, ContactUsResponse
from app.services.email_service import EmailService

router = APIRouter()


@router.post("/contact-us", response_model=ContactUsResponse, status_code=status.HTTP_200_OK)
async def submit_contact_us(payload: ContactUsRequest):
    subject = "MedStream Contact Us Message"

    text_content = (
        "A new contact request has been submitted.\n\n"
        f"Email: {payload.email}\n"
        f"Phone: {payload.phone}\n"
        f"Message:\n{payload.message}\n"
    )

    html_content = (
        "<h2>New Contact Us Message</h2>"
        "<p>A user submitted a contact request from MedStream.</p>"
        f"<p><strong>Email:</strong> {payload.email}</p>"
        f"<p><strong>Phone:</strong> {payload.phone}</p>"
        f"<p><strong>Message:</strong><br>{payload.message.replace(chr(10), '<br>')}</p>"
    )

    sent = await EmailService.send_email(
        to_email=settings.CONTACT_US_RECEIVER_EMAIL,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send contact request email.",
        )

    return {"status": "sent", "detail": "Contact request submitted successfully."}
