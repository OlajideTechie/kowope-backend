# Permissions & Access Control

This document defines role-based permissions for the platform.

## Roles
- Driver
- Agent
- Admin
- Super Admin

---

## Driver 
- Can authenticate via phone number + OTP
- Can view own profile
- Can generate daily tickets
- Can view own ticket history
- Cannot view other drivers
- Cannot modify fees

---

## Agent
- Can authenticate via email and password
- Selects a single area during onboarding (from the Lagos area list)
- Can only validate tickets for drivers in their assigned area
- Validates tickets via QR code scan (`GET /api/v1/ticket/agents/validate`)
- Falls back to phone number lookup if QR is unavailable (`GET /api/v1/ticket/agents/validate/fallback`)
- Cannot validate tickets outside their assigned area (returns 403)
- Can be repositioned to a different area by an admin

---

## Admin
- Can view drivers for all areas
- Invite agents to properly onboard
- Approve or reject agent/driver documents
- Can view all agents and their assigned areas
- Can reposition an agent to a different area
- Can view tickets and payment reports
- Can deactivate agents or drivers

---

## Super Admin 
- Manage platform settings
- Create / Suspend Admins
- Full analytics
- Can perform system-level overrides

---

## Enforcement Strategy
- Role is enforced via request.user.role
- Permissions are enforced using Django REST Framework permissions
- Sensitive actions require explicit role checks
