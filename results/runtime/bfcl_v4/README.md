# Recorded BFCL V4 runtime evidence

These are audits and logs from the completed seven-model run on `vp-dgx-59`. Every model used the frozen case hash `2f7b2ad2d3f0d2610ce303fb3c10e7bdd00d03e4e2f9a7a826bf93293ebcb2e8`, and returned 250 unique first-attempt decisions without request errors or retries. All 250 inputs passed each native preflight without truncation. [Final independent validation](final_validation.json) checks labels, run identities, probabilities, mappings, checkpoint settings, and the saved summaries.

| Model | Environment / identity | Input preflight | Commands / execution |
| --- | --- | --- | --- |
| Laya | [Environment](laya/environment.json) | [Preflight](laya/preflight.json) | [Launch](laya/launch.sh), [identity](laya/launch_identity.json), [evaluation](laya/evaluate_console.log), [server](laya/server.log) |
| Kev | [Environment](kev/environment.json) | [Preflight](kev/preflight.json) | [Launch](kev/launch.sh), [identity](kev/launch_identity.json), [evaluation](kev/evaluate_console.log), [server](kev/server.log) |
| Nimble | [Runtime and commands](nimble_semif_runtime_audit.json), [packages](nimble_packages.txt) | [Preflight](nimble_input_preflight.json) | [Smoke](nimble_smoke.console.log), [full](nimble_full.console.log) |
| SemIf | [Runtime and commands](nimble_semif_runtime_audit.json), [packages](semif_packages.txt) | [Preflight](semif_input_preflight.json) | [Smoke](semif_smoke.console.log), [full](semif_full.console.log) |
| Rizzo | [Environment](rizzo_environment.json), [runtime](rizzo_runtime.json) | [Preflight](rizzo_native_preflight.json) | [Commands](rizzo_eval_commands.json), [evaluation](rizzo_full.console.log), [server](rizzo_server.console.log) |
| Von | [Environment](von/environment.json) | [Preflight](von/preflight.json) | [Launch](von/launch.sh), [identity](von/launch_identity.json), [evaluation](von/evaluate_console.log), [server](von/server.log) |
| NanoJev | [Environment](nanojev_environment.json), [runtime](nanojev_runtime.json) | [Preflight](nanojev_native_preflight.json) | [Commands](nanojev_eval_commands.json), [evaluation](nanojev_full.console.log), [native response probe](nanojev_native_execution_probe.json) |

The three HTTP-model subfolders also contain their separate smoke selections, package checks, final server probes, and validation summaries. Rizzo/NanoJev and Nimble/SemIf used their first two scored cases as smoke tests and resumed the same logs. Laya/Kev/Von ran three separate smoke cases before their 250 scored requests. Warmup therefore differs; timing remains descriptive.

Source helpers preserve the exact native tokenizer/packing checks. They depend on the recorded Linux runtime/cache paths; use the [portable rerun instructions](../../../inference/BFCL_V4.md) for a fresh checkout. The per-case selection logs in the parent results directory are the canonical scoring artifacts. No weights, compiled libraries, virtual environments, credentials, or active runtime state are published.

All owned servers were stopped after completion. All eight GPUs were verified at 0 MiB used and 0% utilization. The independent review found no NanoJev adapter/mapping defect: its poor score remains recorded. Von correctly selected no function on all 50 negatives, but rejected most positive tool cases; its pinned native implementation omits criterion IDs from option-description encoding, as it did in V1. Different native interfaces are part of this comparison.
