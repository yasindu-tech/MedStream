import stripe
from app.config import settings
from decimal import Decimal
from typing import Optional

# Initialize stripe
stripe.api_key = settings.STRIPE_API_KEY

class StripeClient:
    @staticmethod
    def create_checkout_session(
        appointment_id: str,
        amount: Decimal,
        currency: str,
        patient_email: str
    ) -> Optional[dict]:
        """
        Creates a Stripe Checkout Session for the payment.
        """
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=['card'],
                line_items=[{
                    'price_data': {
                        'currency': currency.lower(),
                        'product_data': {
                            'name': f'Appointment Booking - {appointment_id}',
                        },
                        'unit_amount': int(amount * 100), # Amount in cents
                    },
                    'quantity': 1,
                }],
                mode='payment',
                success_url=settings.STRIPE_SUCCESS_URL,
                cancel_url=settings.STRIPE_CANCEL_URL,
                customer_email=patient_email,
                metadata={
                    'appointment_id': appointment_id
                }
            )
            return {
                "id": session.id,
                "url": session.url
            }
        except Exception as e:
            # Re-raise for the service to handle
            raise e

    @staticmethod
    def create_refund(charge_id: str, amount: Decimal) -> Optional[dict]:
        """
        Creates a refund for a successful charge.
        """
        try:
            refund = stripe.Refund.create(
                payment_intent=charge_id, # Or charge id
                amount=int(amount * 100),
            )
            return {
                "id": refund.id,
                "status": refund.status
            }
        except Exception as e:
            raise e

    @staticmethod
    def verify_webhook(payload: str, sig_header: str) -> dict:
        """
        Verifies the webhook signature from Stripe.
        """
        return stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
