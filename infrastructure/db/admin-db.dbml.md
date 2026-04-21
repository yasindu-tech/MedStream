# Admin DB DBML

Source: [init-admin-db.sql](/Users/yasindu/MedStream/infrastructure/db/init-admin-db.sql)

```dbml
Table admin.clinics {
  clinic_id uuid [pk, default: `gen_random_uuid()`]
  clinic_name varchar(255) [not null]
  registration_no varchar(120)
  address text
  phone varchar(30)
  email varchar(255)
  facility_charge numeric(10,2) [default: 0]
  status varchar(30) [not null, default: 'active']
  created_at timestamptz [not null, default: `now()`]

  indexes {
    registration_no [unique]
    email [unique]
  }
}

Table admin.clinic_admins {
  clinic_admin_id uuid [pk, default: `gen_random_uuid()`]
  clinic_id uuid [not null]
  user_id uuid
  status varchar(30) [not null, default: 'active']
  assigned_at timestamptz [not null, default: `now()`]
}

Table admin.clinic_staff {
  staff_id uuid [pk, default: `gen_random_uuid()`]
  clinic_id uuid [not null]
  user_id uuid
  staff_email varchar(255)
  staff_name varchar(255)
  staff_phone varchar(30)
  staff_role varchar(100)
  status varchar(30) [not null, default: 'active']
  created_at timestamptz [not null, default: `now()`]
  updated_at timestamptz
  updated_by varchar(100)
}

Table admin.clinic_staff_history {
  history_id uuid [pk, default: `gen_random_uuid()`]
  staff_id uuid [not null]
  clinic_id uuid [not null]
  user_id uuid
  staff_email varchar(255)
  staff_name varchar(255)
  staff_phone varchar(30)
  staff_role varchar(100)
  status varchar(30) [not null]
  action varchar(50) [not null]
  changed_by varchar(100)
  changed_at timestamptz [not null, default: `now()`]
}

Table admin.doctor_assignment_history {
  history_id uuid [pk, default: `gen_random_uuid()`]
  doctor_id uuid [not null]
  clinic_id uuid [not null]
  action varchar(50) [not null]
  changed_by varchar(100)
  reason text
  changed_at timestamptz [not null, default: `now()`]
}

Table admin.clinic_status_history {
  history_id uuid [pk, default: `gen_random_uuid()`]
  clinic_id uuid [not null]
  old_status varchar(30)
  new_status varchar(30) [not null]
  changed_by varchar(100)
  reason text
  changed_at timestamptz [not null, default: `now()`]
}

Table admin.doctors {
  doctor_id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid
  full_name varchar(255) [not null]
  medical_registration_no varchar(120)
  specialization varchar(120)
  consultation_mode varchar(40)
  verification_status varchar(30) [not null, default: 'verified']
  status varchar(30) [not null, default: 'active']
  verification_documents jsonb
  verification_rejection_reason text
  suspension_reason text
  bio text
  experience_years int
  qualifications text
  profile_image_url text
  consultation_fee numeric(10,2)
  specializations jsonb
  primary_specialization varchar(120)
  created_at timestamptz [not null, default: `now()`]

  indexes {
    medical_registration_no [unique]
  }
}

Table admin.doctor_profile_history {
  history_id uuid [pk, default: `gen_random_uuid()`]
  doctor_id uuid [not null]
  field_name varchar(100) [not null]
  old_value text
  new_value text
  changed_by varchar(100)
  reason text
  changed_at timestamptz [not null, default: `now()`]
}

Table admin.doctor_clinic_assignments {
  assignment_id uuid [pk, default: `gen_random_uuid()`]
  doctor_id uuid [not null]
  clinic_id uuid [not null]
  status varchar(30) [not null, default: 'active']
  assigned_at timestamptz [not null, default: `now()`]

  indexes {
    (doctor_id, clinic_id) [unique]
  }
}

Table admin.doctor_availability {
  availability_id uuid [pk, default: `gen_random_uuid()`]
  doctor_id uuid [not null]
  clinic_id uuid [not null]
  day_of_week varchar(20)
  date date
  start_time varchar(10) [not null]
  end_time varchar(10) [not null]
  slot_duration int [not null, default: 30]
  consultation_type varchar(40)
  status varchar(30) [not null, default: 'active']
  created_at timestamptz [not null, default: `now()`]

  indexes {
    (doctor_id, clinic_id, day_of_week, start_time, consultation_type) [unique]
  }
}

Table admin.doctor_availability_history {
  history_id uuid [pk, default: `gen_random_uuid()`]
  availability_id uuid [not null]
  doctor_id uuid [not null]
  action varchar(50) [not null]
  old_value jsonb
  new_value jsonb
  changed_by varchar(100)
  changed_at timestamptz [not null, default: `now()`]
}

Table admin.doctor_leave {
  leave_id uuid [pk, default: `gen_random_uuid()`]
  doctor_id uuid [not null]
  clinic_id uuid
  start_datetime timestamptz [not null]
  end_datetime timestamptz [not null]
  reason text
  status varchar(30) [not null, default: 'active']
  created_at timestamptz [not null, default: `now()`]
}

Table admin.clinic_payment_accounts {
  payment_account_id uuid [pk, default: `gen_random_uuid()`]
  clinic_id uuid [not null]
  provider_name varchar(120)
  account_reference varchar(255)
  verification_status varchar(30) [not null, default: 'pending']
  connected_at timestamptz [not null, default: `now()`]
}

Ref: admin.clinic_admins.clinic_id > admin.clinics.clinic_id [delete: cascade]
Ref: admin.clinic_staff.clinic_id > admin.clinics.clinic_id [delete: cascade]
Ref: admin.doctor_profile_history.doctor_id > admin.doctors.doctor_id [delete: cascade]
Ref: admin.doctor_clinic_assignments.doctor_id > admin.doctors.doctor_id [delete: cascade]
Ref: admin.doctor_clinic_assignments.clinic_id > admin.clinics.clinic_id [delete: cascade]
Ref: admin.doctor_availability.doctor_id > admin.doctors.doctor_id [delete: cascade]
Ref: admin.doctor_availability.clinic_id > admin.clinics.clinic_id [delete: cascade]
Ref: admin.doctor_availability_history.availability_id > admin.doctor_availability.availability_id [delete: cascade]
Ref: admin.doctor_availability_history.doctor_id > admin.doctors.doctor_id [delete: cascade]
Ref: admin.doctor_leave.doctor_id > admin.doctors.doctor_id [delete: cascade]
Ref: admin.doctor_leave.clinic_id > admin.clinics.clinic_id [delete: cascade]
Ref: admin.clinic_payment_accounts.clinic_id > admin.clinics.clinic_id [delete: cascade]
```
