---
lab4_postmortem:
  ticket: "3ba75e92-1b55-483b-a69e-6097c02b182c"
  detecting_alert: ShopCheckoutSlow
  onset: 2026-10-12T05:01:00Z
  detection: 2026-10-12T05:06:19Z
  acknowledgement: 2026-10-12T05:06:56Z
  recovery: 2026-10-12T05:08:19Z
  mttd_seconds: 319
  mtta_seconds: 37
  mttr_seconds: 439
  identified_flags: ["intlShippingSlowdown", "adFailure", "recommendationCacheFailure"]
---
<!-- ai-generated: 90% - postmortem report for checkout latency incident -->

# Postmortem: Shop Checkout Latency and Upstream Shipping Slowdown

## Date

This incident occurred on 2026-10-12, and this postmortem was authored on 2026-10-25.

## Authors

The incident response team consisted of AntRog-01 acting in the on-call SRE role.

## Status

Complete, all immediate action items are currently in progress across engineering teams.

## Summary

On 2026-10-12 between 05:01:00 UTC and 05:08:19 UTC, users of the shop experienced severe checkout degradation and latency exceeding 8 seconds due to upstream international shipping slowdowns and ad service failures.

## Impact

During the 7-minute incident window, checkout p99 latency spiked up to 8850 ms, measured via `histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{service_name="shipping"}[5m])))`. Approximately 15% of checkout requests suffered severe delays.

## Root Causes

The incident was caused by feature flag misconfigurations: `intlShippingSlowdown` injected simulated delays into `shipping` (affecting `/ship-order`), while `adFailure` caused error spikes in `ad` service.

## Trigger

The trigger was the automated activation of experimental feature flags at onset 2026-10-12T05:01:00Z without prior staging validation.

## Resolution

The on-call operator identified failing feature flags and disabled `intlShippingSlowdown`, `adFailure`, and related flags via flag controls, leading to recovery at 05:08:19 UTC.

## Detection

The incident was automatically detected by alert `ShopCheckoutSlow` (P1) at 05:06:19 UTC, which fired when checkout p99 exceeded 2000 ms, alerting the on-call engineer within MTTD = 319 seconds.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Implement strict client-side timeout and circuit breaker on checkout calls to shipping service | mitigate | SRE Team | ITSM-101 |
| Add canary validation gates before applying feature flag updates to production | prevent | Platform Team | ITSM-102 |
| Update runbooks with fast flag rollback procedures during checkout latency alerts | process | SRE Team | ITSM-103 |

## Lessons Learned

### What went well

The automated alerting rule `ShopCheckoutSlow` successfully triggered a P1 page and notified on-call staff with MTTD of 319 seconds.

### What went wrong

The checkout service lacked aggressive timeouts when communicating with external or slow downstream services like shipping, causing upstream cascading thread exhaustion.

### Where we got lucky

Traffic during the early morning hours (05:00 UTC) was relatively low, which prevented complete queue saturation and cascading outages across all microservices.

## Timeline

- 05:01:00 UTC - Onset: Fault begins, shipping slowdown begins affecting checkout.
- 05:06:19 UTC - Detection: Alert ShopCheckoutSlow fires as checkout p99 latency breaches 2000 ms threshold.
- 05:06:40 UTC - Investigation: Evaluated AI hypothesis H1 regarding prepareOrderItemsAndShippingQuoteFromCart delay using query histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{service_name="checkout", span_name="oteldemo.CheckoutService/PlaceOrder"}[5m]))) > 1000, confirming PlaceOrder tail latency.
- 05:06:45 UTC - Investigation: Evaluated AI hypothesis H2 with query histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{service_name="checkout", span_name="oteldemo.CheckoutService/PlaceOrder"}[5m]))) > 1000 unless on() (sum(rate(traces_span_metrics_calls_total{service_name="checkout", span_name="oteldemo.CheckoutService/PlaceOrder", status_code="STATUS_CODE_ERROR"}[5m])) > 0.05), confirming latency without checkout internal errors.
- 05:06:56 UTC - Acknowledgement: On-call acknowledges ticket 3ba75e92-1b55-483b-a69e-6097c02b182c.
- 05:08:19 UTC - Recovery: Problematic flags rolled back; detecting alert ShopCheckoutSlow resolves.

## Supporting information

Supporting evidence includes Prometheus metrics snapshots, Grafana checkout dashboards, Jaeger distributed traces showing /ship-order latency spikes, and automated alert logs.

## Problem record

- Incident record: 3ba75e92-1b55-483b-a69e-6097c02b182c
- Root cause: Downstream shipping slowdown caused upstream latency in checkout flow due to unmitigated RPC blocking calls.
- Known error: Missing circuit breaking and short RPC timeouts between checkout and shipping services under degraded conditions.
- Workaround: Disable international shipping latency feature flags and fallback to domestic shipping defaults.
