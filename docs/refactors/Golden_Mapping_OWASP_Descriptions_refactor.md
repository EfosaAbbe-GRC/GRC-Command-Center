# Golden Mapping: add official descriptions to the OWASP LLM Top 10 entry (#18)

**Status:** EXECUTED 2026-10-04 (EXECUTE from Efosa). Targeted JSON edit: only this entry changed
(+5/−1 lines; the other six entries verified identical). Dev backend rebuilt; in-container trigger
check over all 50 queries: OWASP fires on **#18 only**, other matches unchanged (incl. the known
#17/#21 misfires); loaded context 269 words, 3 citations. pytest 71 + 1 skipped; dev smoke 44/44.
Measured by v10. **Was:** DRAFT 2026-10-04. Approved in principle by Efosa 2026-10-04
("yes" to v9 decision a). Data-only; needs a backend rebuild (`golden_mappings.json` is baked
into the image); zero Groq tokens to build and test.

## Why

v9 #18 (*"Explain the OWASP Top 10 for LLMs"*): the mapping supplied the ten names only, so the
model listed all ten correctly but refused to explain seven of them (`RAG_Benchmark_Report_v9.md`).
The query asks for an explanation; the mapping should carry one.

## Source

`GRC_Analyst/OWASP Top 10 for LLM Applications 2025.pdf` (official, in corpus), each entry's
"Description" section, PDF pages 7, 11, 15, 20, 23, 26, 30, 33, 36, 39. OWASP content is CC BY-SA
4.0; the text below is a one-sentence condensation of each official description, not a quotation,
and the entry keeps its citations.

## Change — `backend/data/golden_mappings.json`, entry `OWASP_LLM_TOP10_2025`

`canonical_context` becomes:

> The OWASP Top 10 for LLM Applications 2025 lists: **LLM01:2025 Prompt Injection** — user or
> external input alters the model's behaviour or output in unintended ways, even when the input is
> not human-visible; RAG and fine-tuning do not fully prevent it. **LLM02:2025 Sensitive
> Information Disclosure** — the model or application exposes personal data, credentials,
> confidential business data or proprietary details through its output. **LLM03:2025 Supply
> Chain** — third-party models, training data, fine-tuning adapters and deployment platforms can be
> tampered with or poisoned, compromising integrity. **LLM04:2025 Data and Model Poisoning** —
> pre-training, fine-tuning or embedding data is manipulated to introduce vulnerabilities,
> backdoors or biases; an integrity attack. **LLM05:2025 Improper Output Handling** — model output
> is passed downstream without sufficient validation or sanitisation, enabling XSS, CSRF, SSRF,
> privilege escalation or remote code execution. **LLM06:2025 Excessive Agency** — the system is
> granted more functionality, permissions or autonomy than needed, so unexpected or manipulated
> model output can trigger damaging actions. **LLM07:2025 System Prompt Leakage** — system prompts
> contain sensitive information (credentials, connection strings, roles and permissions) that can
> be extracted;
> the system prompt must not be treated as a secret or a security control. **LLM08:2025 Vector and
> Embedding Weaknesses** — weaknesses in how vectors and embeddings are generated, stored or
> retrieved in RAG systems are exploited to inject content, manipulate output or access sensitive
> information. **LLM09:2025 Misinformation** — the model produces false or misleading information
> that appears credible, chiefly through hallucination, leading to security, reputational and
> legal harm. **LLM10:2025 Unbounded Consumption** — the application allows excessive and
> uncontrolled inference, enabling denial of service, financial loss ("denial of wallet") or model
> theft by cloning.

`citations` gains one row: `{"section": "Description sections, LLM01–LLM10", "pdf_pages": "7, 11,
15, 20, 23, 26, 30, 33, 36, 39"}`. Triggers unchanged.

**Checked against the PDF, 2026-10-04:** LLM06's "functionality, permissions or autonomy" is the
entry's own root-cause list (p. 26: "excessive functionality; excessive permissions; excessive
autonomy"); LLM07's "connection strings … roles and permissions" (p. 30); LLM10's "Denial of
Wallet (DoW)" (p. 39).

## Verification (zero tokens)

1. `pytest` — the mapping loader test still passes; JSON valid.
2. In-container trigger check (as in `Golden_Mapping_Enumerations_refactor.md`): the entry fires on
   #18 and its rewordings, and on **no** other benchmark query.
3. Rebuild dev backend; readiness 4/4.

## Measurement

Next benchmark (v10, a weekend): **one variable** = this entry. PII redaction is also new to that
image but is proven not to alter any of the 50 questions (`test_pii` release gate), so it is not a
second variable. **Consequence for the queue:** the corpus removal (HANDOFF 0b) moves to the
following benchmark day (v11), so each stays attributable. Success: #18 `ANSWERED` + `COMPLETE`,
no refusal text, every other grade unchanged.
