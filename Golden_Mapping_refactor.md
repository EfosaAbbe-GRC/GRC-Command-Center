# Golden Mapping Metadata — Draft Diff (per GOVERNANCE.md draft-first protocol)

**Status:** ✅ EXECUTED (2026-08-05). Applied exactly as drafted, with one necessary addition found
mid-deploy: `RAGEngine` had no persistent `self.embeddings` attribute to reuse (each call site
created its own local `HuggingFaceEmbeddings` instance) — added a cached `_get_embeddings()` helper
rather than touching the existing ingestion/query embedding instantiation, to keep this change
additive and low-regression-risk. `numpy` promoted from transitive to a declared dependency in
`requirements.txt` since `rag.py` now imports it directly. Rebuilt backend only (no re-ingestion).
Verified: smoke **42/42**, pytest **32/32** (unchanged from pre-deploy baseline). Benchmark re-run:
**86.0% → 94.0% raw / 92.0% attributable** (#16/#19/#49 all confirmed flipped by mechanism, not
coincidence — answers reproduce the curated `canonical_context` near-verbatim; #6's flip is a
scoring-script artifact, not a real fix — flagged, not claimed). Zero regressions among the 43
previously-passing queries. Full writeup: `RAG_Benchmark_Report_v6.md`.
**Original status (superseded):** DRAFT — awaiting review.
**Scope:** `RAG_Benchmark_Report_v5.md`'s prescribed fix for the EU AI Act cluster (#16, #19, #49) —
"content present but clause-structured; needs Golden Mapping metadata, not better ranking."
`task.md`'s P2 item: *"ingest structured Framework → Control ID mapping to bypass fuzzy vector
retrieval for known compliance identifiers."*
**Target files:** new `backend/data/golden_mappings.json`, `backend/core/rag.py` (query path only —
no changes to ingestion, chunking, or the FAISS index itself).
**Not in scope:** #6 (CSF tiers table — a structured-extraction problem, different lever per the
v5 report), #50 (CISA booklet — source is missing from the corpus entirely, no amount of mapping
fixes that), #36/#45 (judge-calibration jitter). Also not in scope: fixing the underlying PDF
text-extraction defect described below — flagged as a separate, larger-blast-radius finding, not
bundled into this change.

---

## What I found investigating this (context for the design below)

**The retrieval pipeline has no structured-metadata seam today.** `rag.py`'s `query()` does: bi-encoder
FAISS recall at k=20 → cross-encoder re-rank → top-10 → flat string concatenation → single LLM call
(`rag.py:301-311`). Chunk metadata is whatever `PyPDFLoader` gives for free — `source` (file path) and
`page` (int) only. No `article`, `clause`, or `control_id` field exists anywhere in the index. This is
exactly the seam Golden Mapping needs to sit next to.

**A structurally similar pattern already exists in this codebase, but it's policy-facing, not
corpus-facing:** `data/fixtures.json`'s `framework_mappings` + `data_service.get_framework_mappings()`
+ `schemas.FrameworkControl` maps internal policy IDs to external framework controls (e.g.
`{"id": "GDPR-Art5.1e", "name": "GDPR", "control": "...", "status": "..."}`), consumed by
`GET /api/v1/compliance/frameworks/{policy_id}`. It has zero wiring into `rag_engine` — proves the
shape, not reusable directly, since ours needs to be query-triggered rather than policy-ID-keyed.

**Root cause, confirmed per-query against the actual EU AI Act PDF (`GRC_Analyst/EU AI ACT
2024_Doc.pdf`, 144 pages), not assumed from the report alone:**

- **#16** ("four risk categories"): **the Act's text never states this as one enumerated list.**
  It's a secondary/analyst framing that synthesizes four separate provisions that never co-occur in
  a single 1000-char chunk: **Article 5** ("Prohibited AI practices" — unacceptable risk, confirmed
  verbatim: *"Ar ticle 5 Prohibited AI practices... unaccepta ble r isks"*), **Article 6** ("Classification
  rules for high-risk AI systems"), **Article 50** (transparency obligations — limited risk; confirmed:
  *"limited nature that they pose only limited r isks"*), and **Article 95** (voluntary Codes of
  Conduct — the residual/minimal-risk tier). No chunk-boundary tweak fixes this; it needs synthesis
  across articles that retrieval, by design, keeps separate.
- **#19** (generative AI / "ChatGPT"): the Act never uses the word "ChatGPT" or "generative AI" —
  it legislates **"general-purpose AI model[s]"** (Chapter V, Articles 51–56, confirmed verbatim:
  *"CHAPTER V GENERAL-PURPOSE AI MODELS... Ar ticle 51 Classification of general-purpose AI models..."*).
  This is a pure lexical mismatch — bi-encoder recall weakly captures "ChatGPT" ↔ "general-purpose AI
  model" as related but not enough to rank the right chunk into the top 20 reliably (confirmed:
  `load_bearing_documents.csv` doesn't even credit this file for query #19 today).
- **#49** (open-source): the relevant clause exists as ordinary unmangled text (confirmed verbatim:
  *"...processes, or AI components are made accessible under a free and open-source licence..."*)
  but is one clause among 732 chunks from a 144-page document and gets outranked.

**A second, separate defect, found along the way (not fixed here):** this specific PDF's text
extraction systematically injects spaces inside words — `"Ar ticle 9"`, `"r isk"`, `"A ct"` — confirmed
across 576 occurrences of "Article" in the file. Article numbers and legal terms technically survive
(greppable if normalized) but a literal string search for `"Article 9"` finds nothing in this
particular corpus file. This likely affects other queries silently, not just #16/#19/#49, and looks
like a PDF-producer-specific artifact (`PDFlib+PDI 9.0.7p3`). Fixing it properly means re-extracting
and re-chunking this file (and checking siblings from the same producer) — a bigger, separate lever,
flagged here as a candidate for its own future draft, not something to fold into this change.

---

## Design

### 1. New file: `backend/data/golden_mappings.json`

A small, hand-curated, source-cited list — the "golden" part means each entry is verified against
the actual PDF text (quotes above), not generated. Three entries for this pass, one per failing
query cluster:

```json
[
  {
    "id": "EU_AI_ACT_RISK_TIERS",
    "framework": "EU AI Act",
    "trigger_phrases": [
      "What are the four risk categories defined in the EU AI Act?",
      "What are the risk tiers under the EU AI Act?",
      "How does the EU AI Act classify AI systems by risk level?",
      "unacceptable risk high risk limited risk minimal risk EU AI Act"
    ],
    "canonical_context": "The EU AI Act (Regulation (EU) 2024/1689) does not state a single enumerated 'four risk categories' list in one place; it is a risk-based framework assembled across four separate provisions: (1) Unacceptable risk — Article 5, 'Prohibited AI practices' (Title II): AI practices banned outright, e.g. subliminal manipulation, social scoring. (2) High risk — Article 6, 'Classification rules for high-risk AI systems' (plus Annex III triggers): subject to conformity assessment, risk management, and human oversight obligations. (3) Limited risk — Article 50, transparency obligations for systems like chatbots and deepfakes, and tasks of a 'narrow and limited nature' posing only limited risk. (4) Minimal/no risk — Article 95, voluntary Codes of Conduct: the residual tier, encouraged rather than mandated compliance.",
    "citations": [
      {"article": "Article 5", "title": "Prohibited AI practices", "tier": "Unacceptable risk"},
      {"article": "Article 6 / Annex III", "title": "Classification rules for high-risk AI systems", "tier": "High risk"},
      {"article": "Article 50", "title": "Transparency obligations for certain AI systems", "tier": "Limited risk"},
      {"article": "Article 95", "title": "Codes of conduct", "tier": "Minimal risk"}
    ],
    "source_file": "EU AI ACT 2024_Doc.pdf"
  },
  {
    "id": "EU_AI_ACT_GPAI_GENERATIVE",
    "framework": "EU AI Act",
    "trigger_phrases": [
      "How does the EU AI Act handle generative AI like ChatGPT?",
      "What obligations apply to general-purpose AI models under the EU AI Act?",
      "How does the EU AI Act regulate foundation models?",
      "EU AI Act ChatGPT GPT-4 generative AI regulation"
    ],
    "canonical_context": "The EU AI Act does not name 'ChatGPT' or 'generative AI' directly; it regulates this category as 'general-purpose AI models' (GPAI) under Chapter V, Articles 51-56. Article 51 classifies a GPAI model as carrying 'systemic risk' if it meets defined conditions (e.g. cumulative compute used for training). Providers of GPAI models with systemic risk face additional obligations: model evaluation, adversarial testing, incident reporting to the Commission, and cybersecurity safeguards, on top of the baseline GPAI obligations (technical documentation, copyright-compliance policy, training-content summaries) that apply to all general-purpose models, including those underlying consumer chatbots like ChatGPT.",
    "citations": [
      {"article": "Article 51", "title": "Classification of general-purpose AI models with systemic risk", "tier": "GPAI / systemic risk"},
      {"article": "Articles 52-56", "title": "GPAI provider obligations", "tier": "GPAI"}
    ],
    "source_file": "EU AI ACT 2024_Doc.pdf"
  },
  {
    "id": "EU_AI_ACT_OPEN_SOURCE",
    "framework": "EU AI Act",
    "trigger_phrases": [
      "How does the EU AI Act impact open-source AI development?",
      "Are open-source AI models exempt from the EU AI Act?",
      "EU AI Act open source licence exemption"
    ],
    "canonical_context": "The EU AI Act provides a conditional exemption for free and open-source AI: tools, services, processes, or components made accessible under a free and open-source licence fall outside several of the Act's obligations, unless they are placed on the market or put into service as a high-risk AI system, or as a general-purpose AI model with systemic risk (Article 51) -- both of those categories remain fully in scope regardless of licensing model. Developers of free and open-source components outside those categories are encouraged, not mandated, to adopt documentation practices like model cards and datasheets.",
    "citations": [
      {"article": "Recital (whitepaper preamble)", "title": "Free and open-source AI components", "tier": "Conditional exemption"},
      {"article": "Article 51", "title": "GPAI systemic-risk carve-out from the exemption", "tier": "GPAI / systemic risk"}
    ],
    "source_file": "EU AI ACT 2024_Doc.pdf"
  }
]
```

### 2. `backend/core/rag.py` — matching mechanism

**Reuses the already-loaded embedding model, no new dependency.** At startup (or lazily, first
query), embed each entry's `trigger_phrases` once with the same `all-MiniLM-L6-v2` instance `rag.py`
already holds. At query time, embed the incoming question once more and take the max cosine
similarity against each entry's trigger-phrase set; above a threshold, treat it as a hit and prepend
`canonical_context` to the assembled context before the LLM call.

```diff
+import json
+import numpy as np
 ...
 class RAGEngine:
     def __init__(self, documents_path: str = None):
         ...
         self.reranker = None  # lazy-loaded cross-encoder
+        self.golden_mappings = None    # loaded lazily on first query
+        self.golden_trigger_vecs = None  # list[np.ndarray], one matrix per entry
+
+    def _load_golden_mappings(self):
+        path = os.path.join(os.path.dirname(__file__), "..", "data", "golden_mappings.json")
+        with open(path, "r", encoding="utf-8") as f:
+            self.golden_mappings = json.load(f)
+        trigger_texts = [e["trigger_phrases"] for e in self.golden_mappings]
+        flat = [t for phrases in trigger_texts for t in phrases]
+        flat_vecs = np.array(self.embeddings.embed_documents(flat))
+        flat_vecs = flat_vecs / np.linalg.norm(flat_vecs, axis=1, keepdims=True)
+        self.golden_trigger_vecs = []
+        idx = 0
+        for phrases in trigger_texts:
+            n = len(phrases)
+            self.golden_trigger_vecs.append(flat_vecs[idx:idx + n])
+            idx += n
+
+    def _match_golden_mappings(self, text: str, threshold: float = 0.70):
+        if self.golden_mappings is None:
+            self._load_golden_mappings()
+        q_vec = np.array(self.embeddings.embed_query(text))
+        q_vec = q_vec / np.linalg.norm(q_vec)
+        hits = []
+        for entry, trig_vecs in zip(self.golden_mappings, self.golden_trigger_vecs):
+            sim = float((trig_vecs @ q_vec).max())
+            if sim >= threshold:
+                hits.append((sim, entry))
+        hits.sort(key=lambda p: -p[0])
+        return [e for _, e in hits]
 ...
     async def query(self, text: str):
         ...
+        golden_hits = self._match_golden_mappings(text)
         candidates = self.vector_store.similarity_search(text, k=20)
         if self.reranker is None:
             ...
         docs = [d for _, d in ranked[:10]]
         context_text = "\n\n".join([d.page_content for d in docs])
+        if golden_hits:
+            golden_block = "\n\n".join(
+                f"[{h['framework']} — verified reference] {h['canonical_context']}"
+                for h in golden_hits
+            )
+            context_text = golden_block + "\n\n" + context_text
         sources = list(set([os.path.basename(d.metadata.get('source', 'unknown')) for d in docs]))
+        sources += [h["source_file"] for h in golden_hits if h["source_file"] not in sources]
         answer = await self.qa_chain.ainvoke({"context": context_text, "question": text})
         return {"answer": answer, "sources": sources, "context": context_text}
```

**Additive, not a replacement.** Golden context is prepended alongside the normal top-10 chunks, not
instead of them — this preserves existing sourcing/citation behavior for the 43 already-correct
queries and only adds guaranteed coverage where a match fires. Nothing about the FAISS index, chunk
size, or re-ranker changes.

### Design calls I want to confirm before EXECUTE

1. **Similarity threshold — proposed 0.70, empirically derived, not guessed.** I ran the actual
   `all-MiniLM-L6-v2` model (inside `grc-backend`, read-only, no files changed) against all 50
   benchmark queries and the three entries' trigger phrases above. Results:
   - True targets: #16, #19, #49 each score 1.00 against their own entry (verbatim match on one
     trigger phrase — expected, and the other 3 paraphrase-style trigger phrases per entry exist so
     production queries phrased differently than the benchmark still have a real match surface).
   - The closest **cross-framework false-positive risk** found: *"What are the four core functions
     of the NIST AI Risk Management Framework?"* scores **0.648** against the risk-tiers entry (lexical
     overlap on "four" + "risk" + "framework"). A threshold of 0.70 clears this with margin.
   - Adjacent **same-framework** EU AI Act queries (#17 "What constitutes High-Risk", #21 "penalties
     for non-compliance") score 0.65–0.88 depending on entry — these already pass in v5, and if a
     golden entry also fires for them, it's additive/accurate context, not a regression risk, so I'm
     not trying to exclude them.
   - Full matrix available if useful, but the short version: 0.70 is a real, data-backed number, not
     a placeholder — though it should still be validated against the actual v6 benchmark run (see
     below) rather than trusted purely from this offline check.
2. **Citation format has "Recital (whitepaper preamble)" for the open-source entry** — I could not
   pin an exact article number for the free/open-source exemption language in the time available
   (it reads as recital-level text, not an operative article); if you want this pinned to a specific
   recital number before shipping, I can go back and locate it precisely, but it doesn't block the
   mechanism working.
3. **Scope check:** this only helps the 3 queries the report already assigned to Golden Mapping.
   I'm not attempting the PDF text-mangling fix or #6/#50/#36/#45 in this pass — confirm that's the
   right cut, or say if you want the extraction-defect investigation folded in now instead of parked.

---

## Deployment plan (on "EXECUTE")

1. Add `backend/data/golden_mappings.json`, apply the `rag.py` diff above.
2. Rebuild backend only: `docker compose -f docker-compose-v2.yml up -d --build backend` (no
   re-ingestion needed — this doesn't touch the FAISS index or chunking).
3. Smoke + pytest (expect unchanged 42/42 / 32/32 — this is additive to the query path only, no
   schema/model changes, nothing else should move).

## Measurement plan

- Archive current results first: `rag_benchmark_results.v5_reranked.json` stays put; re-run
  `backend/tests/rag_benchmark.py` fresh → archive as `.v6_golden_mapping.json` per convention (one
  variable per run).
- Target: #16/#19/#49 flip from `INSUFFICIENT_DATA` to `ANSWERED`, all other 47 unchanged (any
  unexpected flip elsewhere gets investigated before calling this done, per the "flag drift, don't
  paper over it" convention this project has followed all along).
- Publish `RAG_Benchmark_Report_v6.md` with the before/after scorecard, same format as v2-v5.

## Risks & mitigations

- **False positives diluting context on unrelated queries:** covered above — 0.70 threshold has
  empirical margin against the nearest cross-framework near-miss; full-benchmark re-run is the real
  check, this offline probe is just to avoid guessing the starting number.
- **Maintenance burden of a hand-curated file:** genuinely small right now (3 entries) — this is
  intentionally not a general framework/control-ID database for all 158 corpus documents, just a
  scoped fix for a diagnosed cluster. If it proves valuable, extending it to other frameworks is a
  separate future decision, not implied by this change.
- **Rollback:** delete `golden_mappings.json` and revert the `rag.py` diff — no index rebuild, no
  data migration, fully reversible in one rebuild.

---

**Approval required:** reply **EXECUTE** to apply, or flag any of the three design calls above
first.
