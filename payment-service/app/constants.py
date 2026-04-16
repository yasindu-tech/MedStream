from enum import StringEnum

# Platform hardcoded UUID
PLATFORM_BENEFICIARY_ID = "00000000-0000-0000-0000-000000000001"

# Notification Event Types
class NotificationEvents(StringEnum):
    PAYMENT_CONFIRMED = "payment.confirmed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    APPOINTMENT_BOOKED = "appointment.booked"
