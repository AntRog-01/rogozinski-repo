---
lab3_genai_diff:
  instrumentation: "opentelemetry-instrumentation-genai-openai 1.2b0 (opentelemetry-sdk 1.45.0)"
  spec_ref: "semantic-conventions-genai@e57c543b4889619eb2a05702471937db5119165d"
  attributes:
    - {name: gen_ai.operation.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.provider.name, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.request.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.response.model, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.input_tokens, emitted: true, in_spec: true, stability: development}
    - {name: gen_ai.usage.output_tokens, emitted: true, in_spec: true, stability: development}
---
<!-- ai-generated: 90% - OpenTelemetry GenAI semantic conventions differential analysis -->

# What the library emits, against the spec

## Evaluation Summary

We evaluated the telemetry produced by `opentelemetry-instrumentation-genai-openai` version 1.2b0 against the OpenTelemetry GenAI Semantic Conventions reference `semantic-conventions-genai@e57c543b4889619eb2a05702471937db5119165d`.

All 6 emitted span attributes match the current development specification:
1. `gen_ai.operation.name`: Identifies the GenAI operation type (`chat`). Defined as `development` in the spec.
2. `gen_ai.provider.name`: Specifies the provider (`openai`). Replaced the deprecated `gen_ai.system` attribute. Defined as `development`.
3. `gen_ai.request.model`: Identifies the requested model target (`gpt-4o-mini`). Defined as `development`.
4. `gen_ai.response.model`: Identifies the precise versioned model served in the response (`gpt-4o-mini-2024-07-18`). Defined as `development`.
5. `gen_ai.usage.input_tokens`: Records token consumption for prompt evaluation. Defined as `development`.
6. `gen_ai.usage.output_tokens`: Records token generation count. Defined as `development`.

## Impact on Observability and Dashboards

Building dashboards on top of `development` stability attributes introduces moderate risk of downstream metric breakage when OpenTelemetry stabilizes the specification (e.g., migrating token metrics from span attributes to Prometheus/OTel instruments or renaming keys). However, adopting standardized attributes such as `gen_ai.usage.*_tokens` allows uniform tracking of cost and inference latency across multi-model deployments without proprietary vendor prefixes.
