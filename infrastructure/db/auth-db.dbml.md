# Auth DB DBML

Source: [init-db.sql](/Users/yasindu/MedStream/infrastructure/db/init-db.sql)

```dbml
Table auth.roles {
  role_id integer [pk, increment]
  role_name text [not null, unique]
  description text
  created_at timestamp [not null, default: `now()`]
}

Table auth.users {
  user_id uuid [pk, default: `gen_random_uuid()`]
  full_name text
  email text [not null, unique]
  phone text [unique]
  password_hash text [not null]
  is_verified boolean [not null, default: true]
  account_status text [not null, default: 'ACTIVE']
  suspension_reason text
  created_at timestamp [not null, default: `now()`]
}

Table auth.user_roles {
  user_role_id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid [not null]
  role_id integer [not null]
  created_at timestamp [not null, default: `now()`]

  indexes {
    (user_id, role_id) [unique]
  }
}

Table auth.auth_sessions {
  session_id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid [not null]
  refresh_token text [not null, unique]
  expires_at timestamp [not null]
  is_revoked boolean [not null, default: false]
  created_at timestamp [not null, default: `now()`]
}

Table auth.otp_verifications {
  otp_id uuid [pk, default: `gen_random_uuid()`]
  user_id uuid [not null]
  otp_code text [not null]
  purpose text [not null]
  expires_at timestamp [not null]
  is_used boolean [not null, default: false]
  created_at timestamp [not null, default: `now()`]
}

Ref: auth.user_roles.user_id > auth.users.user_id [delete: cascade]
Ref: auth.user_roles.role_id > auth.roles.role_id [delete: cascade]
Ref: auth.auth_sessions.user_id > auth.users.user_id [delete: cascade]
Ref: auth.otp_verifications.user_id > auth.users.user_id [delete: cascade]
```
