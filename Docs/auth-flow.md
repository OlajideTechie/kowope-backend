# Authentication Flow – Kówópé

Kówópé uses a **phone number–based authentication flow** designed for simplicity and accessibility.

No passwords.
No emails.
No mobile app required.

---

## 🎯 Design Goals

- Minimize friction for drivers
- Work on low-end devices
- Be agent-friendly (assisted onboarding)

---

## 🔐 Authentication Method

**Phone Number + Password**

---

## 🧭 Driver Authentication Flow

### 1️⃣ Driver signs up
- Submits phone number, full name, PIN, license number, document, and **area** (UUID selected from `GET /api/v1/areas`)
- Area is stored as a FK to the central `Area` table

### 2️⃣ OTP is generated
- 6-digit numeric OTP
- Stored temporarily
- Expires after **5 minutes**

### 3️⃣ OTP sent via SMS
- SMS provider is toggleable (Twilio or mock)

### 4️⃣ Driver verifies OTP
- OTP validated
- Phone marked as verified
- Auth tokens returned (auto-login)

### 5️⃣ Subsequent logins
- Driver provides phone number and PIN
- JWT access + refresh tokens returned

---

## 🧭 Agent Onboarding Flow

### 1️⃣ Admin invites agent
- `POST /api/v1/invite-agent` — email is sent with a signed invite link

### 2️⃣ Agent completes registration
- `POST /api/v1/agents/complete-registration`
- Agent submits: full name, **area** (UUID from `/api/v1/areas`), LGA, password, NIN document
- Agent assigned to exactly one area — this enforces their validation boundary

### 3️⃣ Admin approves agent
- `PATCH /api/v1/agents/<id>/approval` — action: `approve` or `reject`
- Approved agents can log in and start validating tickets


---

## 🛂 Admin Authentication

Admins use:
- Email + password
- Role-based access control

Admins **cannot** authenticate via OTP.

---

## 🧩 Security Notes (MVP)

- OTP attempts are rate-limited
- OTP is single-use
- Tokens expire after a defined TTL
- No driverlicense validation in MVP

---

## 🚧 Out of Scope (MVP)

- Biometric verification
- Driver license verification APIs
- Device fingerprinting
- Mobile app deep linking

---

## ✅ Summary

This auth flow prioritizes:
- Speed
- Simplicity
- Real-world usability

Security layers can be expanded post-MVP.
