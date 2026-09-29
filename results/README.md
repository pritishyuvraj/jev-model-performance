# BFCL V1 Jev routing pilot: Laya and Kev

These are the first-step **tool-selection** results for the [250 selected BFCL V1 cases](../data/bfcl_v1/cases.jsonl). Both models received the same `jev.laya` state and choice question. The evaluator withheld source answers and gold labels from their requests. It did not ask either model to fill function arguments or execute a tool.

| Selected cases | Count | Laya typed-decisions | Kev-0.8B |
| --- | ---: | ---: | ---: |
| Choose among multiple offered tools | 150 | 147/150 (98.0%) | 142/150 (94.7%) |
| Call the one offered tool | 50 | 50/50 (100%) | 50/50 (100%) |
| Select no function when the one offered tool is irrelevant | 50 | 43/50 (86.0%) | 49/50 (98.0%) |
| **All cases: tool selection** | **250** | **240/250 (96.0%)** | **241/250 (96.4%)** |

Tool selection is the primary score for Jev's role here. On positive BFCL rows, the model must choose the exact function ID. On no-call rows, `no_tool`, `clarify`, and `cannot_answer` all count as selecting no function. This matters because the BFCL no-call label does not specify which of those three Jev actions to take. Failed requests count as wrong; there were **zero** for either model.

A stricter secondary score requires the exact BFCL-derived action ID on every row, including `no_tool` on no-call rows. Laya scored **228/250 (91.2%)** and Kev scored **224/250 (89.6%)**. On the 50 no-call cases, those exact scores were 31/50 and 32/50 respectively. Laya returned `clarify` 12 times and an offered function 7 times; Kev returned `clarify` 9 times, `cannot_answer` 8 times, and an offered function once. This distinction is why the secondary scores are lower than the tool-selection scores.

The two primary scores differ by **one case**. They were both correct on 232 cases, only Laya was correct on 8, only Kev was correct on 9, and both were wrong on 1. This small difference does not establish that one model is better. The easy one-tool-call stratum also raises the overall score; use the rows above when comparing future models.

## Run identity and files

The runs completed on `vp-dgx-65` (`dgxh100-065`), an H100 DGX, with Laya on GPU 0 and Kev on GPU 1. Laya used native CUDA serving with FP16 automatic mixed precision. Kev used its native PyTorch/CUDA server in FP32 with fused kernels and CUDA graphs disabled. Both servers answered all 250 cases. Their server probes, exact revisions, and result timestamps are in the run metadata.

| Item | Value |
| --- | --- |
| BFCL source | Gorilla V1 tag `v1.0`, commit `9df5c346ee0556c8a7cb09fd7206a39aadd904c2` |
| Selected cases SHA-256 | `68868277c9f10c56706a5d8a1a79a78720582dd731fef414a4b7c4ae366cc602` |
| Laya typed-decisions weights | Standalone revision `1a793eb568e6718f15941d08f85432581df534e3`; served from the identical reviewed bundle revision `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851` |
| Kev-0.8B weights | `jaredpalmer/kev-0.8b@9a45d25eb2ab761841196625383fa1dff0e56c1e` |
| Installed package snapshot | [`requirements.resolved.txt`](../inference/requirements.resolved.txt), SHA-256 `1b6b57b5d6c0958d078e1bca563c80d9c1aa0ccdb854b787a8959a00938659de` |

- Laya: [predictions](bfcl_v1_laya.jsonl), [summary](bfcl_v1_laya.summary.json), [run metadata](bfcl_v1_laya.meta.json).
- Kev: [predictions](bfcl_v1_kev.jsonl), [summary](bfcl_v1_kev.summary.json), [run metadata](bfcl_v1_kev.meta.json).
- [Inference setup and rerun commands](../inference/README.md).

## Scope

This is a derived, selected BFCL routing set, not an official BFCL leaderboard score. It measures neither argument correctness nor end-to-end task completion. Public BFCL questions may have appeared in model training. The current [Kev-0.8B model card](https://huggingface.co/jaredpalmer/kev-0.8b) also warns against relying on this checkpoint for tool-call routing based on its separate When2Call evaluation. Treat these results as a comparison on this exact frozen set, not deployment evidence. Re-evaluate on untouched assistant requests and complete-task outcomes before deciding which model to use in the Jev harness.
