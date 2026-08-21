# [Draft Artifact] Retrieval Tuning Refactor — v1.4 Sprint

**Status:** FULLY EXECUTED 2026-07-18 — Changes 1–2 applied on human approval (44%→72%); Change 3
A/B'd on identical index (82%→86%, +0.94s latency) and **kept** on human approval. See `RAG_Benchmark_Report_v5.md`.
**Deployment addendum:** Re-ingest completed in 685s → 11,884 splits (149/156 files; 7 OneDrive-dehydrated
skips match baseline coverage). During deployment a latent bug was found and fixed in `_hash_index()`:
it included the stale `.integrity` manifest when signing a rebuilt index, guaranteeing an integrity
mismatch on the next verify — the probable true root cause of incident FAISS-INT-001. Fix: exclude
`.integrity` from the signing hash (mirrors the existing exclusion in `_verify_index_hash()`).
**Target file:** `backend/core/rag.py`
**Driver:** Diagnostic v1 (2026-05-24) — all 28 benchmark failures classified **C1**: relevant chunks
exist in the corpus and surface in a wide k=20 scan, but fall below the production k=5 cutoff.
Baseline accuracy: 44% (22/50). Zero corpus gaps, zero LLM over-refusals.

---

## Change 1 — Retrieval depth: k=5 → k=10

Evidence: the exact answer chunk for query #2 (AI RMF Appendix B) sat at rank 10.

```diff
     # 1. Explicit Retrieval
     try:
         # Similarity search is currently synchronous in FAISS-cpu
-        docs = self.vector_store.similarity_search(text, k=5)
+        docs = self.vector_store.similarity_search(text, k=10)
         context_text = "\n\n".join([d.page_content for d in docs])
```

## Change 2 — Chunk size: 600/60 → 1000/100 (two sites)

Evidence: framework definitions (RMF subcategories, ISO clauses, EU AI Act articles) are being
truncated mid-clause at 600 chars, diluting embedding quality and fragmenting answers.

In `initialize_index()`:

```diff
-            text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=60)
+            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
             splits = text_splitter.split_documents(docs)
```

In `_process_documents()`:

```diff
-        text_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=60)
+        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
         texts = text_splitter.split_documents(documents)
```

Context budget after change: 10 chunks × ~1000 chars ≈ 10 KB — trivial for `gemini-2.5-flash`.
Expected index shrink: ~18,337 splits → roughly 11–12k.

## Change 3 (Stretch, opt-in) — Cross-encoder re-rank k=20 → top 10

Bi-encoder (all-MiniLM-L6-v2) recall is good at k=20 but ordering is weak. A cross-encoder
re-scores query+chunk pairs jointly. No new dependency: `sentence-transformers` is already
installed for `HuggingFaceEmbeddings`.

```diff
+from sentence_transformers import CrossEncoder
 ...
 class RAGEngine:
     def __init__(self, documents_path: str = None):
         ...
         self.ingestion_state = IngestionState()
+        self.reranker = None  # lazy-loaded cross-encoder
 ...
     async def query(self, text: str):
         ...
-        docs = self.vector_store.similarity_search(text, k=10)
+        candidates = self.vector_store.similarity_search(text, k=20)
+        if self.reranker is None:
+            self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
+        scores = self.reranker.predict([(text, d.page_content) for d in candidates])
+        ranked = sorted(zip(scores, candidates), key=lambda p: p[0], reverse=True)
+        docs = [d for _, d in ranked[:10]]
         context_text = "\n\n".join([d.page_content for d in docs])
```

Latency cost: ~200–400 ms per query on CPU. Recommendation: apply Changes 1–2 first,
benchmark, then A/B the re-ranker as a second measured step so gains are attributable.

---

## Deployment plan (Phase 1.3, on "EXECUTE")

1. Apply approved diffs to `backend/core/rag.py`.
2. Rebuild backend image: `docker compose -f docker-compose-v2.yml up -d --build backend`.
3. Trigger full re-ingestion via admin JWT → `POST /api/v1/ingest` (~31 min; chunk-size change
   requires a full re-index). Integrity manifest re-signs automatically on save.
4. Preserve the current benchmark artifacts as the v1 baseline (do not overwrite).

## Measurement plan (Phase 1.4)

- Re-run `backend/tests/rag_benchmark.py` — same 50 queries, same pinned `gemini-2.5-flash`.
- Success gate: ≥70% substantive-answer rate (baseline 44%).
- Publish `RAG_Benchmark_Report_v2.md` with per-category before/after scorecard.

## Risks & mitigations

- **Re-index churn on corpus:** corpus is read-only during ingest; `corpus_v1_snapshot/` remains
  the frozen reference. FAISS volume rules per GOVERNANCE §2.4 are unaffected (writes go through
  the existing `save_local` path).
- **Benchmark comparability:** chunk-size change alters the index, so v2 results are compared at
  the *outcome* level (answered vs insufficient), which is chunking-agnostic.
- **Rollback:** revert `rag.py`, re-run ingestion — the deploy path is identical.

---

**Approval required:** reply **EXECUTE** to apply Changes 1–2 (and state whether to include
Change 3 now or A/B it after the first benchmark).
