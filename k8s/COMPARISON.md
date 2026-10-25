<!-- ai-generated: 90% - comparative evaluation of k8sgpt static Kubernetes analyzers versus LLM agentic telemetry root cause analysis -->
# Comparative Analysis: k8sgpt vs. Agentic Prometheus Investigation

## Overview and Methodology

In this evaluation, we compared the diagnostic efficacy of `k8sgpt` (v0.4.39) against an agentic LLM investigation loop (`agent.py` utilizing the Prometheus MCP server `prom_mcp.py`) during our simulated microservices incident on the OpenTelemetry Demo e-commerce stack.

## Analytical Scope and Differences

1. **Infrastructure Health vs. Application Telemetry**:
   `k8sgpt` evaluates cluster-level resource states, analyzing Kubernetes objects such as Pod phases, crash loops, readiness/liveness probe failures, Services without endpoints, and persistent volume binding issues. In our incident, the underlying Kubernetes pods and containers remained in the `Running` and `Ready` states throughout the fault. Because the fault was driven by application-level feature flag misconfigurations (`intlShippingSlowdown`, `adFailure`, `recommendationCacheFailure`), `k8sgpt analyze` returned zero errors (`results: []`). It was completely blind to application-level semantic degradation.

2. **Agentic Prometheus Telemetry Analysis**:
   In contrast, the agentic investigation loop inspected live and recorded Prometheus span metrics (`traces_span_metrics_*`). By iteratively executing PromQL queries across latency histograms and call error rates, the agent was able to pinpoint the exact downstream RPC bottleneck—the `POST /ship-order` latency surge in the `shipping` service—and trace its cascading tail latency impacts on upstream `checkout` and `frontend` calls.

3. **Conclusion and Operational Fit**:
   `k8sgpt` excels at rapidly detecting Kubernetes infrastructure faults (such as OOMKilled containers or misconfigured networking selectors) without requiring domain-specific PromQL knowledge. However, for microservice application-layer degradations, distributed latency anomalies, and feature flag issues, agentic telemetry analysis connected to Prometheus and distributed tracing tools is strictly necessary.
