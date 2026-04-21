# Communication DB DBML

Source: [init-communication-db.sql](/Users/yasindu/MedStream/infrastructure/db/init-communication-db.sql)

```dbml
Table communication.notification_templates {
  template_id uuid [pk, default: `uuid_generate_v4()`]
  event_type varchar(100) [not null, unique]
  channel varchar(50) [not null]
  subject varchar(255)
  body text [not null]
  status varchar(20) [default: 'active']
  created_at timestamptz [default: `current_timestamp`]
}

Table communication.notifications {
  notification_id uuid [pk, default: `uuid_generate_v4()`]
  user_id uuid [not null]
  template_id uuid
  event_type varchar(100)
  channel varchar(50) [not null]
  title varchar(255)
  message text [not null]
  payload jsonb
  status varchar(20) [default: 'queued']
  sent_at timestamptz
  created_at timestamptz [default: `current_timestamp`]
}

Table communication.notification_preferences {
  preference_id uuid [pk, default: `uuid_generate_v4()`]
  user_id uuid [not null, unique]
  email_enabled boolean [not null, default: true]
  sms_enabled boolean [not null, default: true]
  in_app_enabled boolean [not null, default: true]
  updated_at timestamptz [default: `current_timestamp`]
}

Ref: communication.notifications.template_id > communication.notification_templates.template_id [delete: set null]
```
