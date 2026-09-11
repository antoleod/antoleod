# Sources and Claim Map

All technical claims in the short are traceable to public RustChain documentation. URLs below are pinned to repository commit `8c79fba7561283ff8c880258152cd15e2610c312` where practical.

## 1. Physical-hardware attestation before reward enrollment

Source: `docs/attestation-flow.md`  
https://github.com/Scottcjn/Rustchain/blob/8c79fba7561283ff8c880258152cd15e2610c312/docs/attestation-flow.md

Relevant documented behavior:
- attestation proves miners are running on authentic physical hardware;
- the miner collects system information, runs hardware checks, generates a fingerprint, signs it, and submits it to the node;
- the node verifies the signature/fingerprint, checks duplicate hardware, and records a multiplier for valid unique hardware.

Used in script: 0:06–0:16 and 0:40–0:51.

## 2. Fingerprint signals shown in the short

Same source: `docs/attestation-flow.md`.

The documented fingerprint payload includes:
- clock skew / oscillator drift;
- cache timing;
- SIMD identity;
- thermal entropy;
- instruction jitter;
- behavioral heuristics including hypervisor checks.

Used in script: 0:16–0:29.

## 3. Seven fingerprint channels, anti-emulation, fleet detection, server-side verification

Source: `rips/docs/RIP-0308-proof-of-physical-ai.md`  
https://github.com/Scottcjn/Rustchain/blob/8c79fba7561283ff8c880258152cd15e2610c312/rips/docs/RIP-0308-proof-of-physical-ai.md

RIP-0308 states that the PPA design combines seven independent fingerprint channels, server-side verification, fleet detection, and anti-emulation checks. It also identifies RIP-0001 as the Proof-of-Antiquity antiquity-scoring/vintage-multiplier framework and RIP-0200 as the 1-CPU-1-vote attestation model.

Used in script: 0:29–0:40 and as background for the closing comparison.

## Accuracy boundaries

The package intentionally does **not** claim:
- a guaranteed income or ROI;
- a particular RTC price;
- measured energy or e-waste savings;
- that all old hardware automatically qualifies;
- that hardware fingerprinting is impossible to spoof.

The wording describes the documented design and incentive model, not guaranteed economic results.
