# Finance DB DBML

Source: [init-finance-db.sql](/Users/yasindu/MedStream/infrastructure/db/init-finance-db.sql)

```dbml
Enum finance.payment_status {
  pending
  processing
  paid
  failed
  refunded
  expired
}

Enum finance.split_type {
  platform
  clinic
  doctor
}

Enum finance.split_status {
  pending
  settled
  reversed
}

Enum finance.refund_status {
  pending
  approved
  rejected
  processed
  failed
}

Table finance.payments {
  payment_id uuid [pk, default: `gen_random_uuid()`]
  appointment_id uuid [not null, unique]
  patient_id uuid [not null]
  doctor_id uuid [not null]
  clinic_id uuid
  amount numeric(10,2) [not null]
  currency varchar(3) [default: 'LKR']
  doctor_amount numeric(10,2)
  clinic_amount numeric(10,2)
  system_amount numeric(10,2)
  provider_name varchar(50) [default: 'stripe']
  transaction_reference varchar(255)
  status finance.payment_status [default: 'pending']
  failure_reason text
  retry_count integer [default: 0]
  max_retries integer [default: 3]
  expires_at timestamptz
  paid_at timestamptz
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]
}

Table finance.payment_splits {
  split_id uuid [pk, default: `gen_random_uuid()`]
  payment_id uuid [not null]
  split_type finance.split_type [not null]
  beneficiary_id uuid [not null]
  percentage numeric(5,2) [not null]
  amount numeric(10,2) [not null]
  status finance.split_status [default: 'pending']
  created_at timestamptz [default: `now()`]
}

Table finance.refunds {
  refund_id uuid [pk, default: `gen_random_uuid()`]
  payment_id uuid [not null]
  refund_amount numeric(10,2) [not null]
  reason text
  status finance.refund_status [default: 'pending']
  requested_by uuid
  reviewed_by uuid
  refunded_at timestamptz
  created_at timestamptz [default: `now()`]
  updated_at timestamptz [default: `now()`]
}

Ref: finance.payment_splits.payment_id > finance.payments.payment_id [delete: cascade]
Ref: finance.refunds.payment_id > finance.payments.payment_id [delete: cascade]
```
