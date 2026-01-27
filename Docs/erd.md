## Driver
- id
- first_name
- last_name
- phone_number (unique)
- license_number (unique)
- plate_number (unique)
- status (active | inactive)
- created_at

## OTP
- id
- user_id
- otp_hash
- expires_at
- is_used (bool)


## Tickets
- id
- driver_id
- amount
- breakdown (JSON)
- ticket_ref
- created_at
- expired_at


## Payments
- id 
- driver_id
- ticket_id 
- amount
- reference
- status 
- paystack raw data 
- created_at
- updated_at

## FeeConfig
- id
- name
- breakdown (JSON)
- active (bool)
- created_at

## Drivers License
- id (uuid)
- driver_id
- license_number
- uploaded_at

## AdminUser
- id
- role (super_admin | admin | Agent)

## Out Of Scope 

No license expiration checks yet
No biometric / photo capture yet


