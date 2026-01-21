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

### 1️⃣ Driver enters phone number
- Phone number is submitted and password
- System checks if driver exists
- If not, they need to be onboarded 

### 2️⃣ OTP is generated
- 4–6 digit numeric OTP
- Stored temporarily (hashed)
- Expires after **5 minutes**

### 3️⃣ OTP sent via SMS
- SMS contains OTP only
- SMS provider is mocked in MVP

### 4️⃣ Driver verifies OTP
- OTP validated
- Driver session is created
- Auth token is returned

### 5️⃣ Subsequent access
- Driver provides phone number and password
- Driver is verified and logs in if successful


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
