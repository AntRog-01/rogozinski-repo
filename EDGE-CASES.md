---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 25% - structure from course template, analysis and explanations written with assistant assistance -->

# Edge cases in the practice event log

## E1 - clock skew produces a negative lead time

- What the log contains:
  The practice event log contains commit timestamps that are recorded as occurring after the deployment event that actually shipped them to production, caused by unsynchronized system clocks between developer workstations, CI runners, and deployment target environments.
- What a default definition would have done:
  A naive implementation would either silently discard negative duration lead-time pairs or produce a negative time interval, which distorts statistical calculations and can yield a mathematically absurd negative median lead time on the operational dashboard.
- Why the rule is defensible:
  Rule R-08 clamps negative lead times to zero seconds and counts each occurrence in anomalies.negative_lead_time_pairs. This preserves the existence of the delivered commit in the sample without allowing clock skew anomalies to corrupt delivery velocity metrics.

## E2 - a revert of a revert

- What the log contains:
  The log contains commit chains where a commit reverts an earlier commit that itself was a revert of a previous change, resulting in a transitive change resolution path back to the initial unit of work.
- What a default definition would have done:
  A default definition treats every Git commit sha as an independent change, incorrectly inflating the total count of delivered changes to three separate units of work instead of recognizing that the final commit merely restored the original intent.
- Why the rule is defensible:
  Rule R-06 resolves change identity transitively by following reverts links until reaching the original change_id. This correctly models delivery value: reverting an accidental revert restores the original feature, representing one business change rather than three.

## E3 - a hotfix that never touched `main`

- What the log contains:
  Production deployment records include commits authored and released directly on designated hotfix branches (such as `hotfix/2609` or `hotfix/4347`) without having been merged into the default `main` branch prior to deployment.
- What a default definition would have done:
  Conventional delivery tooling often assumes git-flow or trunk-based development and strictly filters commit logs using `branch == "main"`, which completely overlooks urgent hotfixes that reached users directly.
- Why the rule is defensible:
  Rule R-09 explicitly ignores branch naming and branch topology. Delivery metrics measure value reaching real users in the production environment, regardless of whether engineering conventions or Git branch naming standards were followed.

## E4 - a deployment with zero linked commits

- What the log contains:
  The log records production deployment events whose `commits` array is empty, which commonly represents configuration adjustments, infrastructure-only rollouts, automated secrets rotation, or baseline maintenance jobs.
- What a default definition would have done:
  A simplistic lead time calculation would attempt to compute commit-to-deployment intervals without commits, potentially throwing zero-division errors, crashing the ingestion pipeline, or discarding the entire deployment event from release counts.
- Why the rule is defensible:
  Rule R-10 accounts for the deployment in deployment frequency, change fail rate, and rework rate denominators while contributing no lead-time pairs. Production deployments incur release risk regardless of whether application code commits accompanied them.

## E5 - a deployment that failed and never recovered

- What the log contains:
  A failed production deployment exists that has no corresponding incident record resolving it, representing an unrecovered system outage or an incident that remained open past the end of the analysis window.
- What a default definition would have done:
  A standard recovery metric would either drop the failure entirely from reports (hiding unresolved outages) or synthesize an arbitrary recovery timestamp such as the analysis window boundary, artificially penalizing or rewarding the team.
- Why the rule is defensible:
  Rule R-12 counts such events as open failures (`counts.open_failures`), includes them in the change fail rate denominator and numerator, but excludes unrecovered incidents from the median recovery time calculation rather than fabricating fictional recovery dates.

## E6 - overlapping incidents

- What the log contains:
  Multiple distinct incident lifecycles overlap concurrently in time, where a secondary incident opened before a prior incident was successfully resolved.
- What a default definition would have done:
  A naive approach would either aggregate overlapping incident periods by summing raw durations (counting downtime twice for the same wall-clock hours) or attempt complex interval mergers that distort per-deployment failure attribution.
- Why the rule is defensible:
  Rule R-13 attributes recovery strictly per failed deployment rather than per incident, resolving each failed deployment through its earliest covering incident without merging distinct incidents, while tracking concurrency in `anomalies.overlapping_incident_pairs`.

## Gaming demonstration

In this demonstration, we target the throughput metric `deployment_frequency_per_day` using rule R-11. Under rule R-11, deployment frequency is calculated simply as the total count of production deployments divided by the observation window length in days, while rule R-10 permits production deployments to carry empty commit lists (`commits: []`).

We exploited this specification gap by injecting 20 automated zero-commit production deployments distributed evenly across the evaluation window. Concurrently, to simulate delivery deterioration and satisfy the harm criterion under rule R-21, we postponed six critical base production deployments carrying substantial user-facing features (DEP-0033, DEP-0037, DEP-0039, DEP-0040, DEP-0041, DEP-0042) to dates beyond the window boundary.

As a consequence of this gaming strategy:
1. The reported DORA metric `deployment_frequency_per_day` improved by 33.3%, increasing from 2.0 deployments/day to 2.666667 deployments/day, comfortably exceeding the required +25% relative threshold specified in rule R-20.
2. At the same time, actual delivery of real engineering work worsened significantly: `ground_truth.changes_delivered` plummeted from 65 changes down to 56 changes (a 13.8% drop, clearing the rule R-21 requirement of <= 90% base delivery). The median true lead time for delivering changes was similarly delayed.

In a commercial engineering organization, this form of Goodhart's law manifests when executive management establishes raw deployment count or deployment frequency KPIs as targets for team compensation or promotion criteria. Engineering teams respond rationalistically to such incentives by configuring automated scheduled CI/CD jobs that trigger frequent empty or trivial releases to production, while deferring risky, complex, or high-value feature deployments. The management dashboard displays stellar operational throughput ("high elite performance"), yet stakeholders receive fewer working features and suffer delayed software delivery.
