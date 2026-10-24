---
svcdesk_decisions:
  C1: wallclock
  C2: immutable
  C3: vip
---
<!-- ai-generated: 85% - drafted decisions rationale with AI pair programmer -->

# Decisions

## C1 - SLA clock for P1

**Decision:** Priority P1 tickets use a 24/7 wall-clock SLA measurement without pausing outside business hours.

**Rejected alternative:** Pausing P1 tickets outside business hours like priorities P2 through P4.

**Reason:** P1 incidents represent enterprise-wide work stoppage and severe business impact that cannot wait until Monday morning.

**Service owner:** Head of IT Infrastructure and Operations, who manages 24/7 on-call incident response teams.

**Customer outcome:** Critical outages receive round-the-clock incident response within 15 minutes of being reported.

## C2 - Closed tickets and reopening

**Decision:** Closed tickets are completely immutable and cannot be reopened under any circumstances.

**Rejected alternative:** Allowing reporters to reopen closed tickets within a 7-day grace window.

**Reason:** A ticket reaches closed status only after formal user confirmation; recurring issues require fresh tickets to maintain clean audit logs.

**Service owner:** Service Desk Quality and Compliance Lead, responsible for reporting integrity and ITSM audit trails.

**Customer outcome:** Customers receive clear visibility into new work via fresh tickets referencing previous context through the related_to field.

## C3 - VIP reporters and the priority matrix

**Decision:** Tickets submitted by VIP reporters are automatically elevated to priority P2 if the matrix calculation yields P3 or P4.

**Rejected alternative:** Strictly enforcing the standard impact and urgency matrix regardless of reporter status.

**Reason:** Executive leadership incidents carry organizational urgency that warrants faster desk triage regardless of raw technical scope.

**Service owner:** IT Director of Customer Experience and VIP Support, managing executive service agreements.

**Customer outcome:** VIP stakeholders receive expedited ticket handling and rapid escalation for their reported issues.