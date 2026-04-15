# Entity Relationship Overview – Kówópé

---

## User
- id (UUID)
- phone_number (unique, nullable)
- email (unique, nullable)
- role (`driver` | `agent` | `admin` | `super_admin`)
- is_active
- created_at

---

## Area *(common)*
- id (UUID)
- name (unique) — e.g. "Surulere", "Ikeja"
- state — defaults to "Lagos"
- created_at

Seeded with ~80 Lagos areas on deploy. Powers the area dropdown for both driver signup and agent registration.

---

## DriverProfile
- id (UUID)
- user → User (1:1)
- agent → AgentProfile (FK, nullable)
- full_name
- area → **Area (FK)** — selected from dropdown at signup
- lga
- phone_number (unique)
- license_number
- pin_hash
- is_phone_verified
- verified
- created_at / updated_at

---

## AgentProfile
- id (UUID)
- user → User (1:1)
- full_name
- area → **Area (FK, nullable)** — selected from dropdown at registration; one area per agent
- lga
- status (`invited` | `pending_kyc` | `pending_approval` | `approved` | `rejected`)
- invited_by → User (FK, nullable)
- invite_token_used
- nin_document (Cloudinary)
- created_at / updated_at

---

## AdminProfile
- id (UUID)
- user → User (1:1)
- level (`admin` | `super_admin`)
- created_at

---

## OTP
- id (UUID)
- phone_number
- code (6 digits)
- purpose (`signup` | `login` | `pin_reset`)
- is_used
- created_at
- expires_at

---

## Payment
- id (UUID)
- driver → DriverProfile (FK)
- reference (unique)
- amount
- currency
- status (`pending` | `success` | `failed`)
- channel
- payment_date
- gateway_response (JSON)
- authorization_url
- created_at / updated_at

---

## Ticket
- id (UUID)
- payment → Payment (1:1)
- driver → DriverProfile (FK)
- area → **Area (FK)** — inherited from driver's area at ticket creation
- ticket_number (unique) — e.g. `KWP-LAG-20260415-A1B2C3`
- qr_code (UUID, unique)
- status (`ACTIVE` | `INACTIVE` | `REVOKED`)
- valid_for_date
- created_at

---

## DriverDocument
- id (UUID)
- driver → DriverProfile (1:1)
- document_type (`nin` | `license`)
- document_file (Cloudinary)
- status (`pending` | `approved` | `rejected`)
- verified
- uploaded_at
- reviewed_by → AdminProfile (FK, nullable)
- reviewed_at

---

## Key Relationships

```
User ──── DriverProfile ──── Area ◄──── AgentProfile
                │                            │
                ▼                            │
            Payment                    (one area per agent,
                │                       repositioned by admin)
                ▼
            Ticket ──────────────────► Area
```

- A driver belongs to one area; their tickets always carry that area
- An agent is assigned to one area; they can only validate tickets in their area
- Area is the central linking key between drivers, agents, and tickets

---

## Out of Scope (MVP)

- License expiration checks
- Biometric / photo capture
- Plate number tracking
- Fee configuration model
