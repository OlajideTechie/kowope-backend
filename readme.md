## 📜 License References

![Python](https://img.shields.io/badge/Python-3.10-blue)
![Django](https://img.shields.io/badge/Django-5.0-darkgreen)
![DRF](https://img.shields.io/badge/DRF-REST--Framework-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791)
![JWT](https://img.shields.io/badge/JWT-Authentication-orange)
![Paystack](https://img.shields.io/badge/Paystack-Payments-1099BB)
![License](https://img.shields.io/badge/License-MIT-lightgrey)
![Status](https://img.shields.io/badge/Status-Active-success)

# Overview

Kówópé is a driver ticketing system designed to simplify daily road-use payments for commercial drivers.

The goal is to reduce harassment, eliminate cash handling, and provide drivers with a simple, verifiable proof of payment using only a phone number.

---

## Problem
Commercial drivers face daily harassment and inefficiencies due to manual ticketing and fragmented fee collection.

- Cash collections
- Multiple collectors
- No transparency
- No proof of payment

This creates inefficiency, conflict, and lost revenue.

---

## 💡 Solution

Kówópé enables drivers to:
- Register with a phone number
- Generate a daily ticket after payment
- Receive a ticket reference via SMS
- Use that reference as proof of payment

Admins can:
- Manage drivers
- Configure fees
- View tickets and payments

---

## Core Features
Kówópé provides a mobile-first web platform for:
- Driver onboarding
- Daily ticket generation
- Transparent fee handling

## MVP Scope
- Web-based driver access (mobile friendly)
- Payment processing logic 
- Agent-assisted ticket generation
- Daily ticket issuance via phone number

## Tech Stack
- **Backend**: Django + Django REST Framework
- **Database**: PostgreSQL (SQLite for local dev)
- **Auth**: Phone number + OTP
- **Notifications**: SMS (mocked in MVP)
- **Deployment**: Render

## Authentication
- Phone number based login
- One-time PIN (OTP) for verification
- Session-based access (MVP)

## Folder Structure

```
kowope-backend/
│
├── manage.py
├── README.md
├── requirements.txt
├── .env.example
│
├── config/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── drivers/
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── tests.py
│   │
│   ├── tickets/
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── tests.py
│   │
│   ├── fees/
│   │   ├── models.py
│   │   ├── views.py
│   │   └── tests.py
│   │
│   └── admins/
│       ├── views.py
│       └── permissions.py
│
├── common/
│   ├── utils.py
│   ├── sms.py   
│   └── permissions.py
│
├── docs/
│   ├── erd.md
│   ├── auth-flow.md
│   └── api-contracts.md
│
└── tests/
    └── test_health.py
```


## Local Setup

```bash
# Clone the repository locally
git clone <repo-url>
cd kowope


# Set up virtual environment
python -m venv venv

# Activate virtual environment
source venv/bin/activate  

# or 
env\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Run migration
python manage.py migrate

# Start the server
python manage.py runserver
```

### Access Swagger docs at

```http://127.0.0.1:8000/swagger/```
