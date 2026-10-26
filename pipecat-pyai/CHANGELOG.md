# Changelog

## 0.1.4 — unreleased

- Initialize STT model and language settings explicitly for Pipecat 1.14.
- Use public audio-context completion signals in pipeline tests.
- Require Pipecat 1.14 or newer for this source candidate.

## 0.1.3 — 2026-09-24

- Preserve pending speech commits when an automatic transcript final arrives.
  Stop now waits for the requested commit completion while delivering all earlier
  and later transcript text, including empty completion acknowledgements.
- Retain compatibility with older services that omit a completion reason or
  report `commit`. The existing five-second stop timeout remains unchanged.

The matching Hear completion-correlation repair is deployed. This release does
not change recognition models or claim new latency or accuracy measurements.
