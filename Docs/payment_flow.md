# Payment & Ticket Flow System

This repository/module implements a **ticket lifecycle and payment processing system** with a focus on **lazy expiration** and **payment cutoff logic**. The system ensures tickets expire automatically and enforces cutoff times before payment processing.

---

## Table of Contents

- [Overview](#overview)
- [Ticket Lifecycle](#ticket-lifecycle)
- [Payment Flow](#payment-flow)
- [Lazy Expiration Mechanism](#lazy-expiration-mechanism)
- [Cutoff Time Check](#cutoff-time-check)
- [Key Lessons & Design Considerations](#key-lessons--design-considerations)

---

## Overview

The system handles:

1. Ticket creation and management.
2. Automatic expiration of tickets **once per day** via a lazy check.
3. Payment initialization while respecting ticket expiration and payment cutoff rules.

It is optimized to **avoid unnecessary database operations** when no expired tickets exist.

---

## Ticket Lifecycle

Tickets move through the following states:

1. **Active Ticket** – Newly created and valid for usage.
2. **Lazy Expiration Check** – A daily check updates expired tickets.
3. **Inactive Ticket** – Expired tickets are marked as inactive and cannot be used for payment.

**Notes:**

- Expiration occurs **once per day** when the system checks tickets.
- The system does not rely on a cron job; the lazy check triggers when a payment is being initialized.

---

## Payment Flow

1. User initializes payment via API.
2. The system first checks if there are **any expired tickets** and marks them inactive.
3. Payment cutoff logic is applied:
   - Payments **before cutoff** → processed successfully.
   - Payments **after cutoff** → blocked.
4. Payment is recorded and ticket is associated with the transaction.

---

## Lazy Expiration Mechanism

The lazy expiration approach:

- Runs **once per day**.
- Only updates tickets with `expiry_date < today` and `status = ACTIVE`.
- Avoids running on every request, minimizing DB operations.
- Ensures expired tickets are updated before payment initialization.

---

## Cutoff Time Check

- Payments are only processed **before a defined daily cutoff time**.
- This prevents late payments from being processed outside business rules.
- Integrates seamlessly with lazy expiration to maintain data integrity.

---

## Key Lessons & Design Considerations

- **Lazy updates vs cron jobs**: Improved reliability and reduced dependencies on external schedulers.
- **Atomic updates**: Using `.update()` ensures database changes happen efficiently.
- **Defensive coding**: Prevented errors during migrations by skipping operations if tables are unavailable.
- **System thinking**: Ensured ticket expiration, payment, and cutoff rules are interlinked and predictable.

---

## Diagram

![Ticket Expiration & Payment Cutoff Flow](image.png)

---