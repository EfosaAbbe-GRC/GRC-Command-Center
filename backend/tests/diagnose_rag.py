#!/usr/bin/env python3
"""
GRC Command Center — RAG Accuracy Diagnostic Tool (v4)
Isolates corpus gaps, retrieval failures, and model reasoning issues.
Pins model to gemini-2.5-flash and enforces strict schema validation.
"""
import os
import sys
import json
import time
import asyncio
from typing import List, Dict, Any

# Ensure backend modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

# Load parent .env file to ensure correct GOOGLE_API_KEY is retrieved on host
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_env = os.path.join(os.path.dirname(root_dir), ".env")
if os.path.exists(root_env):
    load_dotenv(root_env, override=True)

from core.config import settings
from core.rag import rag_engine, PRODUCTION_PROMPT_TEMPLATE
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ─── Configuration & Templates ──────────────────────────────────────────────

# Pinned model name for reproducibility (corresponds to the baseline benchmark)
MODEL_NAME = "gemini-2.5-flash"

JUDGE_PROMPT_TEMPLATE = """You are evaluating whether a retrieved document chunk contains information
sufficient to answer a GRC compliance question.

Question: {query}
Retrieved chunk: {chunk_text}

Classify the chunk as exactly one of:
- "relevant": Contains direct, sufficient information to answer the question
- "partial": Contains related information that partially addresses the question
- "irrelevant": Does not contain information useful for answering

Respond with only the label."""

RELAXED_PROMPT_TEMPLATE = """Using the following context, answer the question. If the context contains any relevant information, provide a partial answer rather than refusing.

Context:
{context}

Question: {question}

Auditor Response:"""

# ─── Schema Validation ────────────────────────────────────────────────────────

def validate_schema(entry: Dict[str, Any]):
    """Strict schema validation to prevent malformed data insertion."""
    required_keys = ["query_id", "query_text", "expected_category", "outcome", "corpus_scan", "retrieval", "llm", "diagnosis"]
    for k in required_keys:
        if k not in entry:
            raise ValueError(f"Schema Violation: Missing key '{k}'")
            
    if entry["outcome"] not in ["ANSWERED", "INSUFFICIENT_DATA"]:
        raise ValueError(f"Schema Violation: Invalid outcome '{entry['outcome']}'")
        
    if entry["diagnosis"] not in ["A", "B", "C1", "C2", "SUCCESS"]:
        raise ValueError(f"Schema Violation: Invalid diagnosis '{entry['diagnosis']}'")
        
    corpus_scan_keys = ["keyword_hits", "wide_k20_retrieval_sample"]
    for k in corpus_scan_keys:
        if k not in entry["corpus_scan"]:
            raise ValueError(f"Schema Violation: Missing key 'corpus_scan.{k}'")
            
    retrieval_keys = ["chunks", "judge_verdict"]
    for k in retrieval_keys:
        if k not in entry["retrieval"]:
            raise ValueError(f"Schema Violation: Missing key 'retrieval.{k}'")
            
    if entry["retrieval"]["judge_verdict"] not in ["relevant", "partial", "irrelevant"]:
        raise ValueError(f"Schema Violation: Invalid judge_verdict '{entry['retrieval']['judge_verdict']}'")
        
    for chunk in entry["retrieval"]["chunks"]:
        for ck in ["chunk_id", "score", "text"]:
            if ck not in chunk:
                raise ValueError(f"Schema Violation: Missing key 'retrieval.chunks.{ck}'")
                
    llm_keys = ["full_prompt", "response", "latency_ms"]
    for k in llm_keys:
        if k not in entry["llm"]:
            raise ValueError(f"Schema Violation: Missing key 'llm.{k}'")

# ─── Helper Functions ──────────────────────────────────────────────────────────

def get_expected_category(query_id: int) -> str:
    if 1 <= query_id <= 8:
        return "NIST AI RMF / CSF 2.0"
    elif 9 <= query_id <= 15:
        return "ISO 27001 / 42001"
    elif 16 <= query_id <= 23:
        return "EU AI Act / OWASP"
    elif 24 <= query_id <= 28:
        return "GDPR / Privacy"
    elif 29 <= query_id <= 33:
        return "TPRM"
    elif 34 <= query_id <= 40:
        return "GRC Engineering / IT Audit"
    elif 41 <= query_id <= 50:
        return "Emerging AI Risks / Strategy"
    return "Unknown"

def extract_keyword_hits(query: str, text: str) -> List[str]:
    stopwords = {"what", "how", "why", "who", "when", "where", "which", "does", "doesnt", "should", "could", "would", "is", "are", "was", "were", "the", "and", "or", "but", "a", "an", "of", "to", "in", "on", "at", "for", "with", "about", "against", "into", "through", "during", "before", "after", "above", "below", "from", "up", "down", "out", "over", "under", "again", "further", "then", "once", "here", "there", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", "will", "just", "don", "shouldve", "now", "d", "ll", "m", "o", "re", "ve", "y", "ain", "aren", "couldn", "didn", "doesn", "hadn", "hasn", "haven", "isn", "ma", "mightn", "mustn", "needn", "shan", "shouldn", "wasn", "weren", "won", "wouldn"}
    words = [w.strip("?,.:;!\"'()[]").lower() for w in query.split()]
    meaningful_words = [w for w in words if len(w) > 3 and w not in stopwords]
    text_lower = text.lower()
    hits = [w for w in meaningful_words if w in text_lower]
    return list(set(hits))

async def judge_chunk(query: str, chunk_text: str, judge_chain) -> str:
    try:
        response = await judge_chain.ainvoke({"query": query, "chunk_text": chunk_text})
        verdict = response.strip().strip("'\"").lower()
        if "relevant" in verdict:
            return "relevant"
        elif "partial" in verdict:
            return "partial"
        else:
            return "irrelevant"
    except Exception as e:
        print(f"Judge call error: {e}", file=sys.stderr)
        return "irrelevant"

# ─── Main Diagnostic Runner ───────────────────────────────────────────────────

async def main():
    # Robust Path Detection for FAISS Index (Container vs Host)
    faiss_path = None
    possible_faiss_paths = [
        "faiss_index",
        "../faiss_index",
        "/app/faiss_index",
        os.path.join(os.path.dirname(root_dir), "faiss_index")
    ]
    for path in possible_faiss_paths:
        if os.path.exists(path) and os.path.exists(os.path.join(path, "index.faiss")):
            faiss_path = path
            break

    if not faiss_path:
        print(f"Error: Vector index not found in possible locations: {possible_faiss_paths}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading FAISS index from: {faiss_path}")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    rag_engine.vector_store = FAISS.load_local(faiss_path, embeddings, allow_dangerous_deserialization=True)
    rag_engine._init_chain()

    # Robust Path Detection for Benchmark results
    benchmark_file = None
    possible_benchmark_paths = [
        "rag_benchmark_results.json",
        "../rag_benchmark_results.json",
        "/app/rag_benchmark_results.json",
        os.path.join(os.path.dirname(root_dir), "rag_benchmark_results.json")
    ]
    for path in possible_benchmark_paths:
        if os.path.exists(path):
            benchmark_file = path
            break

    if not benchmark_file:
        print(f"Error: Baseline results file not found in: {possible_benchmark_paths}", file=sys.stderr)
        sys.exit(1)
        
    print(f"Loading baseline results from: {benchmark_file}")
    with open(benchmark_file, "r") as f:
        benchmark_data = json.load(f)
        
    results_list = benchmark_data.get("results", [])
    if not results_list:
        print("Error: No results found in the baseline file.", file=sys.stderr)
        sys.exit(1)

    # Initialize Gemini models (pinned to gemini-2.5-flash, temperature 0.0)
    print(f"Initializing ChatGoogleGenerativeAI models pinned to {MODEL_NAME}...")
    judge_prompt = ChatPromptTemplate.from_template(JUDGE_PROMPT_TEMPLATE)
    relaxed_prompt = ChatPromptTemplate.from_template(RELAXED_PROMPT_TEMPLATE)
    
    # Judge & Relaxed LLM instances
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=settings.GOOGLE_API_KEY, temperature=0.0)
    judge_chain = judge_prompt | llm | StrOutputParser()
    relaxed_chain = relaxed_prompt | llm | StrOutputParser()

    diagnostic_results = []
    category_summary = {"A": 0, "B": 0, "C1": 0, "C2": 0, "SUCCESS": 0}

    print(f"\n🚀 Running GRC RAG Diagnostic ({len(results_list)} queries)...\n")
    print(f"{'ID':<3} | {'Original Outcome':<18} | {'Diagnosis':<10} | {'Latency':<8}")
    print("-" * 50)

    for i, res in enumerate(results_list):
        query_id = res["id"]
        query_text = res["query"]
        original_outcome = res["outcome"]
        original_response = res.get("answer", "")
        
        # Pull original latency in milliseconds directly from the JSON to avoid re-run drift
        latency_ms = int(res.get("latency", 0.0) * 1000)

        # Step 2: Wide retrieval similarity search (k=20)
        # similarity_search_with_score returns Tuple[Document, L2_distance]
        wide_docs_with_scores = rag_engine.vector_store.similarity_search_with_score(query_text, k=20)
        
        # Step 3: Run LLM-as-judge relevance classification over all 20 chunks
        wide_verdicts = []
        for idx, (doc, score) in enumerate(wide_docs_with_scores):
            verdict = await judge_chunk(query_text, doc.page_content, judge_chain)
            wide_verdicts.append(verdict)

        # Apply Decision Rule: Category A (Not in Corpus) is assigned if and only if all 20 chunks are irrelevant
        all_irrelevant = all(v == "irrelevant" for v in wide_verdicts)
        
        # Check standard top-5 chunk subset
        top5_verdicts = wide_verdicts[:5]
        top5_chunks_formatted = []
        for idx, (doc, score) in enumerate(wide_docs_with_scores[:5]):
            top5_chunks_formatted.append({
                "chunk_id": f"{os.path.basename(doc.metadata.get('source', 'unknown'))}_p{doc.metadata.get('page', 0)}_c{idx}",
                "score": round(float(score), 4),
                "text": doc.page_content
            })
            
        # Determine standard retrieval judge verdict
        if "relevant" in top5_verdicts:
            top5_judge_verdict = "relevant"
        elif "partial" in top5_verdicts:
            top5_judge_verdict = "partial"
        else:
            top5_judge_verdict = "irrelevant"

        # Step 4: Run C1/C2 Discriminator Logic or assign B/A
        if original_outcome == "ANSWERED":
            diagnosis = "SUCCESS"
        elif all_irrelevant:
            diagnosis = "A"
        elif top5_judge_verdict in ["relevant", "partial"]:
            # Context contains relevant details but outcome was INSUFFICIENT_DATA -> discriminator run
            relaxed_context = "\n\n".join([doc.page_content for doc, _ in wide_docs_with_scores[:5]])
            relaxed_response = await relaxed_chain.ainvoke({"context": relaxed_context, "question": query_text})
            
            if relaxed_response.strip().startswith("INSUFFICIENT_DATA"):
                diagnosis = "C2"  # LLM failed to reason even with relaxed prompt
            else:
                diagnosis = "C1"  # Relaxed prompt succeeded -> prompt was too strict
        else:
            # Info exists in the k=20 set (not all_irrelevant) but not in standard top-5
            diagnosis = "B"

        category_summary[diagnosis] += 1

        # Populate output schema (full text + score + verdict for auditability)
        wide_sample_data = []
        for idx, (doc, score) in enumerate(wide_docs_with_scores):
            wide_sample_data.append({
                "rank": idx,
                "score": round(float(score), 4),
                "text": doc.page_content,
                "judge_verdict": wide_verdicts[idx]
            })
            
        full_context_for_hits = "\n\n".join([doc.page_content for doc, _ in wide_docs_with_scores])
        keyword_hits = extract_keyword_hits(query_text, full_context_for_hits)

        # Reconstruct the exact full prompt that was sent to the LLM (verbatim from core/rag.py template)
        context_text = "\n\n".join([doc.page_content for doc, _ in wide_docs_with_scores[:5]])
        full_system_prompt = PRODUCTION_PROMPT_TEMPLATE.format(context=context_text, question=query_text)

        entry = {
            "query_id": query_id,
            "query_text": query_text,
            "expected_category": get_expected_category(query_id),
            "outcome": original_outcome,
            "corpus_scan": {
                "keyword_hits": keyword_hits,
                "wide_k20_retrieval_sample": wide_sample_data
            },
            "retrieval": {
                "chunks": top5_chunks_formatted,
                "judge_verdict": top5_judge_verdict
            },
            "llm": {
                "full_prompt": full_system_prompt,
                "response": original_response,
                "latency_ms": latency_ms
            },
            "diagnosis": diagnosis
        }

        # Enforce strict schema validation before storing
        try:
            validate_schema(entry)
        except ValueError as val_err:
            print(f"\n❌ SCHEMA VIOLATION HALT: {val_err}", file=sys.stderr)
            sys.exit(1)

        diagnostic_results.append(entry)

        # Write checkpoint every 10 queries
        if (i + 1) % 10 == 0:
            checkpoint_path = os.path.join(root_dir, "diagnostic_results.partial.json")
            with open(checkpoint_path, "w") as f:
                json.dump({
                    "results": diagnostic_results,
                    "completed": i + 1,
                    "total": len(results_list),
                    "summary": category_summary
                }, f, indent=4)
            print(f"Checkpoint saved: {i + 1}/{len(results_list)} queries processed.")

        # Print progress to stdout per query
        print(f"{query_id:<3} | {original_outcome:<18} | {diagnosis:<10} | {latency_ms / 1000.0:<7.2f}s")

    # Save to diagnostic_results.json
    output_path = os.path.join(root_dir, "diagnostic_results.json")
    with open(output_path, "w") as f:
        json.dump({"results": diagnostic_results}, f, indent=4)

    # Clean up partial checkpoint if run completes successfully
    checkpoint_path = os.path.join(root_dir, "diagnostic_results.partial.json")
    if os.path.exists(checkpoint_path):
        try:
            os.remove(checkpoint_path)
        except Exception:
            pass

    # Print summary
    print("\n" + "=" * 50)
    print("DIAGNOSTIC COMPLETE")
    print(f"Total Queries Analyzed: {len(results_list)}")
    print(f"Summary Outcomes:")
    print(f" - SUCCESS (Baseline Answered): {category_summary['SUCCESS']}")
    print(f" - Category A (Not in Corpus):   {category_summary['A']}")
    print(f" - Category B (Retrieval Fail):   {category_summary['B']}")
    print(f" - Category C1 (Strict Prompt):  {category_summary['C1']}")
    print(f" - Category C2 (Model Reasoning): {category_summary['C2']}")
    print(f"\nResults saved to: {output_path}")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
