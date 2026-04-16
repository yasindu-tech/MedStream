class EventTypes:
    APPOINTMENT_BOOKED = "appointment.booked"
    APPOINTMENT_CANCELLED = "appointment.cancelled"
    APPOINTMENT_RESCHEDULED = "appointment.rescheduled"
    APPOINTMENT_REMINDER = "appointment.reminder"
    ACCOUNT_VERIFICATION = "account.verification"
    ACCOUNT_PASSWORD_RESET = "account.password_reset"
    ACCOUNT_APPROVED = "account.approved"
    ACCOUNT_SUSPENDED = "account.suspended"
    PRESCRIPTION_AVAILABLE = "prescription.available"
    PAYMENT_CONFIRMED = "payment.confirmed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"

    @classmethod
    def all(cls):
        return [
            cls.APPOINTMENT_BOOKED,
            cls.APPOINTMENT_CANCELLED,
            cls.APPOINTMENT_RESCHEDULED,
            cls.APPOINTMENT_REMINDER,
            cls.ACCOUNT_VERIFICATION,
            cls.ACCOUNT_PASSWORD_RESET,
            cls.ACCOUNT_APPROVED,
            cls.ACCOUNT_SUSPENDED,
            cls.PRESCRIPTION_AVAILABLE,
            cls.PAYMENT_CONFIRMED,
            cls.PAYMENT_FAILED,
            cls.PAYMENT_REFUNDED,
        ]
