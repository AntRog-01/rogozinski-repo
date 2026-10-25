---
lab4_comms:
  awareness: 2026-10-12T05:06:19Z
  detection: 2026-10-12T05:06:19Z
  classification: 2026-10-12T05:15:00Z
  nis2:
    early_warning_due: 2026-10-13T05:06:19Z
    notification_due: 2026-10-15T05:06:19Z
    notification_sent: 2026-10-12T12:00:00Z
    final_report_due: 2026-11-12T12:00:00Z
  ksc:
    early_warning_due: 2026-10-13T05:06:19Z
    notification_due: 2026-10-15T05:06:19Z
    notification_sent: 2026-10-12T12:00:00Z
    final_report_due: 2026-11-12T12:00:00Z
  dora:
    initial_due: 2026-10-12T09:15:00Z
    initial_sent: 2026-10-12T08:00:00Z
    intermediate_due: 2026-10-15T08:00:00Z
    intermediate_sent: 2026-10-13T10:00:00Z
    final_due: 2026-11-13T10:00:00Z
  log:
    - {at: "2026-10-12T05:30:00Z", to: "CSIRT NASK", what: "NIS2 and KSC early warning regarding critical checkout latency degradation"}
    - {at: "2026-10-12T08:00:00Z", to: "Financial Supervision Authority (KNF)", what: "DORA initial notification with preliminary impact assessment"}
    - {at: "2026-10-12T12:00:00Z", to: "CSIRT NASK", what: "NIS2 and KSC full incident notification confirming workaround and recovery"}
---
<!-- ai-generated: 90% - regulatory communications log and deadline analysis -->

# Communications log: the regulators' clocks

## The three instants you defend

1. **Awareness (NIS2)**: `2026-10-12T05:06:19Z`. At this moment, the on-call engineer received the P1 pager alert `ShopCheckoutSlow` confirming significant customer-facing degradation on the shop.
2. **Detection (KSC)**: `2026-10-12T05:06:19Z`. Under the Polish Krajowy System Cyberbezpieczeństwa act ("od momentu jego wykrycia"), the incident was detected by the automated monitoring system when checkout tail latency exceeded 2 seconds.
3. **Classification (DORA)**: `2026-10-12T05:15:00Z`. Following initial triage, evaluation of payment flow impact, and consultation of major ICT incident criteria, the incident was formally classified as a major incident.

## The log

| Time (UTC) | Recipient | Content | Regulatory Clock |
|---|---|---|---|
| 2026-10-12T05:30:00Z | CSIRT NASK | Early warning of significant checkout latency | NIS2 Art. 23(4)(a) & KSC Art. 11 |
| 2026-10-12T08:00:00Z | KNF (Competent Authority) | DORA initial report on checkout delay | DORA Art. 19(4)(a) |
| 2026-10-12T12:00:00Z | CSIRT NASK | Incident notification confirming root cause and fix | NIS2 Art. 23(4)(b) & KSC Art. 11 |
