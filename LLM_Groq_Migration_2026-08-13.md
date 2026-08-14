# Migration: Gemini → Groq for the RAG/chat LLM

**Status:** ✅ EXECUTED (2026-08-13). User stopped paying for the Google Cloud project behind
`GOOGLE_API_KEY`; the key started returning `403 PERMISSION_DENIED` ("Your project has been denied
access") and, once that cleared, the free tier's `429 RESOURCE_EXHAUSTED` (20 requests/day for
`gemini-2.5-flash`) — this is what caused the ~23-minute backend block found during the 2026-08-13
dogfooding session's boot-ritual verification (see `MEMORY.md`'s gotchas). Rather than regenerate
another Gemini key with the same free-tier ceiling, migrated the LLM call to Groq.

**What did NOT change:** embeddings (`all-MiniLM-L6-v2`, local HuggingFace), the reranker
(`cross-encoder/ms-marco-MiniLM-L-6-v2`, local), FAISS, or the retrieval/golden-mapping pipeline.
Gemini was only ever used for the final generation step — one `ChatGoogleGenerativeAI` instantiation
in `core/rag.py`. Because that's wired through LangChain's provider-agnostic chat-model interface
(`prompt | model | StrOutputParser()`), the swap was a small, contained change, not a rewrite.

## Changes

- **`backend/requirements.txt`**: `langchain-google-genai` → `langchain-groq` (also fixed a
  pre-existing duplicated comment line while touching this section).
- **`backend/core/config.py`**: added `GROQ_API_KEY`. `GOOGLE_API_KEY` kept, but now only read by
  the parked, Gemini-pinned diagnostic scripts (see Open Items below) — not the live app.
- **`backend/core/rag.py`**:
  - `self.api_key` now reads `settings.GROQ_API_KEY`.
  - `_init_chain()`: `ChatGoogleGenerativeAI(model="gemini-2.5-flash", ...)` →
    `ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=self.api_key, max_retries=2, timeout=30)`.
    **The `max_retries`/`timeout` bounds are new, not just a provider swap** — the old integration had
    neither, which is exactly what let a struggling API key block the whole single-threaded backend
    for ~23 minutes (the SDK's own retry/backoff had no ceiling). Bounded now regardless of provider.
  - Error-message strings and a stale docstring (`"embeds them into FAISS using Gemini Embeddings"`
    — already wrong before this change; embeddings have always been local HuggingFace, not Gemini)
    corrected while touching these lines.
- **`backend/main.py`**: readiness check detail text and the root endpoint's `"engine"` field updated
  to say Groq / Llama 3.3 70B instead of Gemini.
- **`docker-compose-v2.yml`, `docker-compose.test.yml`**: added `GROQ_API_KEY=${GROQ_API_KEY}`
  passthrough alongside the existing (now-unused-by-the-app) `GOOGLE_API_KEY` line.
- **`CLAUDE.md`**: architecture header updated (`LLM: Groq (Llama 3.3 70B Versatile)`).
- **`.env`**: `GROQ_API_KEY` added (a dedicated key, not reused from the user's other project, for
  clean per-project usage attribution and independent revocation).

## Why Groq over local (Ollama)

Discussed directly with the user: local via Ollama is the more durable, zero-external-dependency
option long-term (and would match the project's existing local embeddings/reranker/FAISS stack), but
a 7-8B local model would likely land meaningfully below the 92% RAG benchmark baseline, and needs
real local hardware. Groq's free tier (hosted Llama models, OpenAI-compatible, genuinely free) was
picked as the lower-friction first move most likely to hold the existing benchmark number. Local
remains the fallback if Groq's free tier ever becomes a problem.

## Verification

Rebuilt both `grc-backend` (dev stack) and `grc-backend-test` (isolated test stack) images from the
updated `requirements.txt`. Confirmed live, not just import-clean:

- `/api/v1/readiness` on both stacks: `llm_api_key` → `"ready", "Groq API key configured"`.
- Live `/api/v1/chat` call on the dev stack answered correctly with real corpus citations (3 lines of
  defense question, sources included `GRC_Excellence_RoadMap.pdf` etc.).
- **`smoke_test.py`: 43/43 passed** against the Groq-backed test stack — including the
  `active-auditor` agent-execution check that previously blocked for ~23 minutes under the failing
  Gemini key. This run completed in **~31 seconds**, matching the original ~43s baseline documented
  for `active-auditor` (2026-08-06), confirming the block was the API key, not the architecture.
- **`pytest`: 32/32 passed**, in 76s (vs. 108s on the same suite minutes earlier against the failing
  Gemini-backed run) — no regressions, and meaningfully faster.

## Open items

- **`backend/tests/diagnose_rag.py` and `backend/tests/validate_diagnostic.py` still import
  `ChatGoogleGenerativeAI` directly** and are now non-functional (no working `GOOGLE_API_KEY`). These
  are the RAG-diagnostic/judge-calibration tooling, not part of the live app — already flagged as
  low-priority parked items in `HANDOFF.md`/`JUDGE_CALIBRATION_v2.md`. Left untouched deliberately
  (out of scope for this pass); migrate them to Groq too if a future benchmark/diagnostic run is
  needed.
- **RAG benchmark (`rag_benchmark.py`, expect 46/50 / 92%) has not been re-run against Groq.** It
  exercises `/chat` (already confirmed live above), so it should work, but the actual accuracy number
  under Llama 3.3 70B vs. Gemini 2.5 Flash is unverified — worth running before trusting the "92%"
  figure still holds. `rag_benchmark.py` itself has no direct Gemini dependency (calls the API, not
  the SDK), so no code change needed there, just a re-run.
- A stray secret-hygiene note: an earlier `grep` in this session accidentally printed the old
  (already non-functional) `GOOGLE_API_KEY` value into the conversation transcript. User was told
  directly and advised to revoke/rotate it in Google Cloud Console as good practice regardless.
