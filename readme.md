# Kowope Backend

![Python](https://img.shields.io/badge/Python-3.11-blue)
![Django](https://img.shields.io/badge/Django-5.2-darkgreen)
![DRF](https://img.shields.io/badge/DRF-REST--Framework-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791)
![JWT](https://img.shields.io/badge/JWT-Authentication-orange)
![Paystack](https://img.shields.io/badge/Paystack-Payments-1099BB)
![License](https://img.shields.io/badge/License-MIT-lightgrey)
![Status](https://img.shields.io/badge/Status-Active-success)

Kowope is a driver ticketing system designed to simplify daily road-use payments for commercial drivers. It reduces cash handling, eliminates harassment, and gives drivers a verifiable proof of payment using only a phone number.

---

## Problem

Commercial drivers face daily harassment and inefficiencies due to manual ticketing and fragmented fee collection — cash collections, multiple collectors, no transparency, and no proof of payment.

---

## Solution

**Drivers** can:
- Register with a phone number and complete OTP verification
- Purchase a daily ticket via Paystack
- Receive a ticket reference as proof of payment

**Agents** can:
- Be invited by admins and onboarded with KYC
- Manage and verify drivers in their assigned area

**Admins** can:
- Invite and manage agents
- Approve or reject driver and agent documents
- View tickets, payments, and driver reports
- Deactivate agents or drivers

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2 + Django REST Framework |
| Database | PostgreSQL (production), SQLite (local dev) |
| Auth | Phone + OTP (drivers), Email + Password + JWT (admin/agent) |
| Payments | Paystack |
| File Storage | Cloudinary |
| SMS | Twilio (toggleable) |
| Deployment | Render |
| Docs | drf-spectacular (Swagger) |

---

## Project Structure

```
kowope-backend/
├── authentication/        # User, DriverProfile, AgentProfile, AdminProfile models + auth views
│   └── management/
│       └── commands/
│           ├── create_admin.py   # Create admin via CLI
│           └── seed_admin.py     # Auto-seed admin on deploy (reads from env vars)
├── agents/                # Agent invite + registration flow
├── common/                # Shared Area model, seeded with Lagos areas, area list endpoint
├── payments/              # Paystack payment integration
├── ticket/                # Daily ticket issuance and verification
├── middleware/            # Custom permission classes (IsAdmin, IsAgent, IsDriver)
├── services/              # Business logic (OTP, SMS, invite agent, Paystack)
├── utils/                 # Phone normalization, payment helpers
├── kowope/                # Django settings and root URLs
├── conftest.py            # Pytest fixtures (throttle disabling, shared setup)
└── manage.py
```

---

## Area System

Areas are seeded from a central `common.Area` model populated with ~80 Lagos areas. Both drivers and agents select from the same dropdown:

- **Driver** selects one area at signup → area FK on `DriverProfile`
- **Agent** selects one area at registration → area FK on `AgentProfile`
- **Ticket** inherits the driver's area → area FK on `Ticket`
- **Validation**: agents can only verify tickets whose area matches their own

To fetch the dropdown list: `GET /api/v1/areas` (public)

---

## API Endpoints

### Driver Auth
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/driver/signup` | Public | Driver registration (area UUID required) |
| POST | `/api/v1/auth/driver/login` | Public | Driver login (phone + PIN) |
| POST | `/api/v1/auth/driver/verify-otp` | Public | OTP phone verification |
| POST | `/api/v1/auth/driver/resend-otp` | Driver | Resend OTP |
| POST | `/api/v1/auth/driver/reset-pin` | Public | Reset driver PIN |
| POST | `/api/v1/auth/driver/logout` | Driver | Logout |
| GET  | `/api/v1/auth/driver/me` | Driver | Driver profile |

### Admin & Agent Auth
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/admin/login` | Public | Admin login |
| POST | `/api/v1/auth/agent/login` | Public | Agent login |

### Agent Management
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/invite-agent` | Admin | Invite a new agent |
| POST | `/api/v1/agents/complete-registration` | Public | Agent completes registration with area + KYC |
| PATCH | `/api/v1/agents/<id>/approval` | Admin | Approve or reject agent |

### Payments & Tickets
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/payment/` | Driver | Initiate ticket payment |
| GET  | `/api/v1/ticket/all` | Driver | Dashboard — active + recent tickets |
| GET  | `/api/v1/ticket/agents/validate` | Agent | Validate ticket by QR code |
| GET  | `/api/v1/ticket/agents/validate/fallback` | Agent | Validate ticket by driver phone number |

### Common
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/areas` | Public | List all Lagos areas (for dropdowns) |

Full interactive docs at `/` or `/api/docs/` after running locally.

---

## Local Setup

```bash
# Clone the repo
git clone <repo-url>
cd kowope-backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# Install dependencies
pip install -r requirements.txt

# Copy and fill in environment variables
cp .env.example .env

# Run migrations
python manage.py migrate

# Create an admin user for local testing
python manage.py create_admin --email admin@kowope.com --password yourpassword

# Start the server
python manage.py runserver
```

Swagger docs: `http://127.0.0.1:8000/`

---

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for local, `False` for production |
| `DATABASE_URL` | PostgreSQL URL (leave unset to use SQLite locally) |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary config |
| `CLOUDINARY_API_KEY` | Cloudinary config |
| `CLOUDINARY_API_SECRET` | Cloudinary config |
| `ENABLE_SMS_PROVIDER` | `True` to send real SMS via Twilio |
| `ENABLE_EMAIL_PROVIDER` | `True` to send real emails via SMTP |
| `RETURN_OTP_IN_RESPONSE` | `True` to expose OTP in response (staging only) |
| `RETURN_INVITE_LINK` | `True` to expose invite URL in response (staging only) |
| `FRONTEND_DOMAIN` | Base URL used to build agent invite links |
| `ADMIN_EMAIL` | Seed admin email (used by `seed_admin` on Render deploy) |
| `ADMIN_PASSWORD` | Seed admin password (used by `seed_admin` on Render deploy) |

---

## Running Tests

```bash
pytest
```

Coverage report is generated in `htmlcov/` and `coverage.xml`.

---

## Deployment (Render)

Set all env vars in Render → Environment, then set the pre-deploy command:

```bash
python manage.py migrate && python manage.py seed_admin
```

`seed_admin` is idempotent — it creates the super admin on first deploy and skips silently on all subsequent ones.
