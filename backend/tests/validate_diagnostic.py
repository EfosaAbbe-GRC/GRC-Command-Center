import os
import sys
import json
import asyncio
from datetime import datetime

# Note: stdout strings are ASCII-only for Windows console compatibility (cp1252)
# Ensure backend modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
root_env = os.path.join(os.path.dirname(root_dir), ".env")
if os.path.exists(root_env):
    load_dotenv(root_env, override=True)

from core.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Pinned model name for reproducibility
MODEL_NAME = "gemini-2.5-flash"

# Relaxed Prompt Template for C1/C2 validation
RELAXED_PROMPT_TEMPLATE = """Using the following context, answer the question. If the context contains any relevant information, provide a partial answer rather than refusing.

Context:
{context}

Question: {question}

Auditor Response:"""

# Locked Judge Prompt Template with self-bias skepticism instruction
JUDGE_PROMPT_TEMPLATE = """You are reviewing the output of an AI system for correctness and context alignment.
Be especially skeptical of plausible-sounding answers, as the system being evaluated
may have pulled information from its pre-training weights rather than the provided context.

Question: {query}
Context provided: {context}
LLM Response: {response}

Classify the LLM Response as exactly one of:
- "ANSWERED": The response provides a substantive, correct answer drawn only from the provided context.
- "REFUSED": The response explicitly states it cannot answer, that the context is insufficient, or that information is missing.
- "HALLUCINATED": The response provides an answer or specific facts that are not supported by the provided context.

Respond with only the label."""

async def main():
    # Robust Path Detection for diagnostic_results.json
    original_path = None
    uncalibrated_path = None
    
    # Try finding either diagnostic_results.json or diagnostic_results.v1_uncalibrated.json
    possible_folders = [
        root_dir,
        os.path.dirname(root_dir),
        os.getcwd()
    ]
    
    for folder in possible_folders:
        cand_orig = os.path.join(folder, "diagnostic_results.json")
        cand_uncal = os.path.join(folder, "diagnostic_results.v1_uncalibrated.json")
        if os.path.exists(cand_uncal):
            uncalibrated_path = cand_uncal
            original_path = cand_orig
            break
        elif os.path.exists(cand_orig):
            uncalibrated_path = cand_uncal
            original_path = cand_orig
            break
            
    if not original_path or (not os.path.exists(original_path) and not os.path.exists(uncalibrated_path)):
        print(f"Error: diagnostic_results.json not found in possible locations: {possible_folders}", file=sys.stderr)
        sys.exit(1)
        
    if os.path.exists(original_path) and not os.path.exists(uncalibrated_path):
        print(f"Renaming {original_path} to {uncalibrated_path}...")
        os.rename(original_path, uncalibrated_path)
        
    print(f"Loading uncalibrated results from: {uncalibrated_path}")
    with open(uncalibrated_path, "r") as f:
        data = json.load(f)
    results = data.get("results", [])
    
    # Filter for all failed queries (initial diagnosis C1 or C2)
    failed_queries = [r for r in results if r["diagnosis"] in ["C1", "C2"]]
    print(f"Loaded {len(failed_queries)} failed queries for validation.")
    
    llm = ChatGoogleGenerativeAI(model=MODEL_NAME, google_api_key=settings.GOOGLE_API_KEY, temperature=0.0)
    relaxed_prompt = ChatPromptTemplate.from_template(RELAXED_PROMPT_TEMPLATE)
    judge_prompt = ChatPromptTemplate.from_template(JUDGE_PROMPT_TEMPLATE)
    
    relaxed_chain = relaxed_prompt | llm | StrOutputParser()
    judge_chain = judge_prompt | llm | StrOutputParser()
    
    validated_entries = []
    summary_counts = {"ANSWERED (True C1)": 0, "REFUSED (True A/B Gap)": 0, "HALLUCINATED (True A/B or C2)": 0}
    
    print(f"\nRunning expanded validation on all {len(failed_queries)} failed queries (Host Mode)...\n")
    print(f"{'ID':<3} | {'Category':<28} | {'Judge Verdict':<20}")
    print("-" * 65)
    
    for i, q in enumerate(failed_queries):
        query_id = q["query_id"]
        query_text = q["query_text"]
        
        # Build context from top 5 chunks
        top5_chunks = q["retrieval"]["chunks"]
        context = "\n\n".join([c["text"] for c in top5_chunks])
        
        # Build exact prompts for audit records
        full_relaxed_prompt = RELAXED_PROMPT_TEMPLATE.format(context=context, question=query_text)
        
        # Run relaxed prompt
        start_time = datetime.utcnow().isoformat() + "Z"
        try:
            response = await relaxed_chain.ainvoke({"context": context, "question": query_text})
        except Exception as e:
            response = f"ERROR executing relaxed query API call: {e}"
        end_time = datetime.utcnow().isoformat() + "Z"
        
        # Run three-category judge on the response
        full_judge_prompt = JUDGE_PROMPT_TEMPLATE.format(query=query_text, context=context, response=response)
        try:
            judge_response = await judge_chain.ainvoke({"query": query_text, "context": context, "response": response})
            judge_verdict = judge_response.strip().strip("'\"").upper()
        except Exception as e:
            judge_verdict = "ERROR"
            judge_response = f"ERROR executing judge API call: {e}"
            
        # Standardize classification
        if "ANSWERED" in judge_verdict:
            label = "ANSWERED (True C1)"
        elif "HALLUCINATED" in judge_verdict:
            label = "HALLUCINATED (True A/B or C2)"
        else:
            label = "REFUSED (True A/B Gap)"
            
        summary_counts[label] += 1
        print(f"{query_id:<3} | {q['expected_category'][:28]:<28} | {label:<20}")
        
        validated_entries.append({
            "query_id": query_id,
            "query_text": query_text,
            "expected_category": q["expected_category"],
            "relaxed_prompt": {
                "full_text": full_relaxed_prompt,
                "response": response,
                "model": MODEL_NAME,
                "temperature": 0.0,
                "start_time": start_time,
                "end_time": end_time
            },
            "judge": {
                "full_text": full_judge_prompt,
                "response": judge_response,
                "verdict": judge_verdict
            },
            "final_validated_diagnosis": label
        })
        
        # Rate-limiting cushion
        await asyncio.sleep(2.0)
        
    output_path = os.path.join(os.path.dirname(uncalibrated_path), "validation_results.json")
    with open(output_path, "w") as f:
        json.dump({
            "validation_run": validated_entries,
            "summary": {
                "total_failures_audited": len(failed_queries),
                "true_c1_answered": summary_counts["ANSWERED (True C1)"],
                "true_ab_refused": summary_counts["REFUSED (True A/B Gap)"],
                "true_ab_or_c2_hallucinated": summary_counts["HALLUCINATED (True A/B or C2)"],
                "percentages": {
                    "true_c1": round((summary_counts["ANSWERED (True C1)"] / len(failed_queries)) * 100, 2),
                    "true_ab_refusal": round((summary_counts["REFUSED (True A/B Gap)"] / len(failed_queries)) * 100, 2),
                    "true_hallucination": round((summary_counts["HALLUCINATED (True A/B or C2)"] / len(failed_queries)) * 100, 2)
                }
            }
        }, f, indent=4)
        
    print("\n" + "=" * 50)
    print("VALIDATION RUN COMPLETE")
    print(f"Total Failures Audited: {len(failed_queries)}")
    print(f" - True C1 (ANSWERED):       {summary_counts['ANSWERED (True C1)']} ({round((summary_counts['ANSWERED (True C1)'] / len(failed_queries)) * 100, 1)}%)")
    print(f" - True A/B Gap (REFUSED):    {summary_counts['REFUSED (True A/B Gap)']} ({round((summary_counts['REFUSED (True A/B Gap)'] / len(failed_queries)) * 100, 1)}%)")
    print(f" - Hallucinated (outside weight): {summary_counts['HALLUCINATED (True A/B or C2)']} ({round((summary_counts['HALLUCINATED (True A/B or C2)'] / len(failed_queries)) * 100, 1)}%)")
    print(f"Results saved to: {output_path}")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())
