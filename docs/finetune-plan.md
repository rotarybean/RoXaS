# LoRA fine-tune plan (RoXaS)

Status: **proposed**. Baseline numbers are from `software/rag/eval_generate.py` on the 42-question eval sets
(stock Qwen2.5-0.5B-Instruct, retrieval v5): 26 pass, 5 generation fail, 5 retrieval fail, 6 no-refusal.

## What the fine-tune is for
Behavior only. Facts stay in SQLite and the retrieved context. The baseline shows exactly four behavior problems:

| Problem | Baseline | Training signal |
|---|---|---|
| Answers instead of refusing when the manuals lack the topic or code | 0 of 6 refused | `code_not_found`, `unknown_topic` examples |
| Picks the wrong number among near neighbors (3.3 vs 3.5 L, standard vs max gap) | 2 failures | authored spec examples with distractor figures in context |
| Misreads flattened spec tables (`3.3 {3.5, 2.9}`) | 2 failures | same set; table-shaped contexts |
| Picks the wrong row among several part numbers | 1 failure | **not trained**: code picks the row (see below) |

## Design decisions
1. **Pre-retrieval, no model-issued tool calls.** Code routes (DTC lookup, parts search, manual search) and the model
   only reads the context it is given. A 0.5B model emits unreliable tool calls; deterministic routing already works
   and the eval harness is built on it. This replaces the "consistent tool calls" item in the handoff. Revisit only if
   multi-step questions turn out to matter.
2. **Part numbers and DTC meanings are composed by code, not generated.** The model made wrong-part numbers look
   confident. The runtime fills a template from the matched row (number, description, page, OCR confidence) and the
   model, if used at all, only phrases it. Rows below `high` confidence, or not yet human-verified, say "check catalog
   page N".
3. **One prompt everywhere.** `software/rag/prompt.py` is used by eval, SFT data and the CM5 runtime.

## Data format
Chat JSONL, one example per line: `{"cat": ..., "messages": [system(+CONTEXT), user, assistant]}`. The context is
produced by the real `retrieve()` + `context_for_model()`, so training sees what serving sees. Loss on assistant
tokens only. Never put facts in the assistant text that are not in that example's context.

| Category | Source | Target count |
|---|---|---|
| `dtc_meaning`, `dtc_causes` | dtc table, templates | about 340 (built) |
| `code_not_found` | random unused codes | about 130 (built) |
| `unknown_topic` | brands absent from every manual | about 100 (built) |
| `spec`, `procedure` | authored Q/A over real context windows, each answer's numbers checked against the context | 150 to 300 (to do) |

Refusals must stay at or under about 25% of the set; the built categories alone are 40%, so the spec/procedure set
is required before training, not optional. Watch `bad_refusal` in the eval.

Leakage guard: DTC codes, brand terms and question words from the eval sets are excluded from training. The
untouched final test set is still to be written (the held-out set was used for tuning).

## Training settings (RTX 4060 8 GB)
- Method: LoRA, not full fine-tuning (full fine-tuning of 0.5B with Adam is about 9 GB, too much).
- LoRA: r 16, alpha 32, dropout 0.05, all linear layers (q, k, v, o, gate, up, down).
- bf16, gradient checkpointing on, max length 1536 tokens (context is about 800).
- Batch 4 per step x grad accumulation 4 = 16 effective; lr 2e-4, cosine, 3% warmup; 3 epochs; seed fixed.
- Expected: about 3 to 4 GB VRAM and 10 to 20 minutes for about 1,000 examples. Evaluate after each epoch and keep the
  best by dev loss and the eval sets, not the last.
- Export: merge adapter, convert to GGUF, quantize Q4_K_M (llama.cpp `convert_hf_to_gguf.py`, `llama-quantize`).
  Re-run the eval on the quantized file, since Q4 can change refusal behavior.

## Success criteria (before the CM5 benchmark)
- Refusal on unanswerable questions: at least 5 of 6 (baseline 0 of 6), with `bad_refusal` at most 1.
- Spec and procedure pass rate at least 90% when the evidence is in context (baseline about 70%).
- Zero part numbers or DTC meanings produced by the model outside the code path.
