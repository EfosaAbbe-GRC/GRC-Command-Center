#!/usr/bin/env python3
"""
GRC Command Center — RAG Accuracy Benchmarker
Evaluates retrieval and generation quality across 50 compliance queries.
Categorizes responses into ANSWERED, INSUFFICIENT_DATA, or ERROR.
"""
import requests
import json
import time
import os
import sys

# Configuration
BASE_URL = "http://localhost:8001/api/v1"
ADMIN_USER = "admin"
ADMIN_PASS = "grc-admin-2026"
OUTPUT_FILE = "rag_benchmark_results.json"

# Groq binds four limits at once on openai/gpt-oss-120b (free tier): 30 RPM, 1,000 RPD,
# 8,000 TPM and 200,000 TPD -- whichever is reached first returns 429. Only RPD and TPM
# appear in response headers; there is NO TPD header, so remaining daily budget cannot be
# checked before a run. Limits are scoped to the Groq ORGANIZATION, not to this project or
# this API key, so other projects on the same account spend the same budget.
#
# This delay addresses TPM only. Cost per query, DERIVED from the v7 archive rather than
# estimated (50 real answers, avg 1,707 chars, max 5,455) plus the fixed parts of the
# request -- 10 reranked chunks x 1,000 chars of context, this module's prompt template,
# the question -- at ~4 chars/token:
#     ~3,073 tokens typical, ~4,010 worst case.
# Unpaced, the loop ran at 3.56 queries/min in v7 -- 10,900-14,300 tokens/min against an
# 8,000 TPM ceiling -- which is what produced v8's intermittent failures from query #11.
# At ~17s natural latency plus this delay the run sits at 1.54 queries/min:
#     ~4,744 tokens/min typical, ~6,191 worst case -- inside the limit with headroom.
#
# It does NOT help with TPD. A full 50-query run costs ~154,000 tokens typical and up to
# ~200,500 worst case, i.e. 77-100% of the entire 200,000/day organization-wide budget.
# That is why "no other project needs tokens today" is a hard gate, not a nicety.
#
# Note: ChatGroq is configured max_retries=2, so a throttled query can fire up to 3 calls,
# spending request budget (1,000 RPD) and retry tokens beyond the figures above.
# See docs/refactors/Benchmark_Pacing_refactor.md.
PACING_SECONDS = float(os.getenv("GRC_BENCH_PACING", "22"))

# /chat returns HTTP 200 with an error message in the BODY when the LLM call fails, so
# status_code alone cannot detect failure. Keep in sync with core/agent.py's
# _ENGINE_FAILURE_MARKERS -- deliberately duplicated rather than imported, because this
# script runs on the HOST against the container's exposed port and cannot import core.*
# (that pulls in langchain and the whole backend stack). Four rarely-changing strings;
# the duplication is the cheaper risk. See Benchmark_Scorer_Honesty_refactor.md.
ENGINE_FAILURE_MARKERS = (
    "i encountered an error processing your request",
    "security alert: knowledge base integrity check failed",
    "error loading index:",
    "rag engine not initialized",
)


def is_engine_failure(answer: str) -> bool:
    """An engine failure is neither a refusal nor an answer."""
    if not answer or not answer.strip():
        return True
    low = answer.lower()
    return any(m in low for m in ENGINE_FAILURE_MARKERS)

# 50 Targeted GRC Queries
QUERIES = [
    # NIST AI RMF / CSF 2.0
    "What are the four core functions of the NIST AI Risk Management Framework?",
    "What is the difference between AI-specific risks and traditional IT risks according to NIST AI RMF?",
    "How does NIST CSF 2.0 address supply chain risk management?",
    "List the core outcomes of the 'Govern' function in NIST AI RMF.",
    "Explain the 'Map' function in NIST AI RMF 1.0.",
    "What are the Tier 1 thru Tier 4 implementation levels in NIST CSF 2.0?",
    "How should organizations manage bias in AI models according to NIST?",
    "What is the role of 'Measure' in the AI RMF lifecycle?",
    
    # ISO 27001 / 42001
    "What are the key changes in ISO 27001:2022 compared to the 2013 version?",
    "Explain the purpose of Annex A.5.7 (Threat Intelligence) in ISO 27001.",
    "What is ISO/IEC 42001 and how does it relate to AI Management Systems?",
    "List the mandatory documentation required for ISO 27001 certification.",
    "How does ISO 27001:2022 address cloud security controls?",
    "What is the significance of Clause 4 (Context of the Organization) in ISO 27001?",
    "What are the key AI governance controls specified in ISO 42001?",
    
    # EU AI Act / OWASP
    "What are the four risk categories defined in the EU AI Act?",
    "What constitutes a 'High-Risk' AI system under the EU AI Act?",
    "Explain the OWASP Top 10 for LLMs (Large Language Models).",
    "How does the EU AI Act handle generative AI like ChatGPT?",
    "What are the transparency requirements for AI systems targeting humans?",
    "What are the penalties for non-compliance with the EU AI Act?",
    "List three strategies to mitigate Prompt Injection according to OWASP.",
    "What is 'Model Inversion' in the context of OWASP AI security?",
    
    # GDPR / Privacy
    "How does GDPR apply to automated decision-making and profiling?",
    "What is a DPIA (Data Protection Impact Assessment) and when is it required?",
    "List the seven core principles of GDPR.",
    "How does 'Privacy by Design' apply to AI model training?",
    "What are the requirements for cross-border data transfers under GDPR?",
    
    # TPRM
    "What are the key steps in the TPRM lifecycle?",
    "How should an organization assess the security of an AI SaaS vendor?",
    "What is a SOC 2 Type II report and why is it important for TPRM?",
    "List the primary risk factors when onboarding a fourth-party vendor.",
    "How do you verify GDPR compliance for a non-EU third party?",
    
    # GRC Engineering / IT Audit
    "What are ITGC (IT General Controls) and give three examples.",
    "Explain the 'Three Lines of Defense' model in GRC.",
    "How do you perform a gap assessment between NIST CSF and ISO 27001?",
    "What is the difference between a Key Risk Indicator (KRI) and a KPI?",
    "What are the common pitfalls in SOX internal controls implementation?",
    "List the steps for an effective incident response plan per NIST 800-61.",
    "How do you manage evidence chain-of-custody during a compliance audit?",
    
    # Emerging AI Risks / Strategy
    "What is 'Shadow AI' and how can organizations detect it?",
    "What are the ethical considerations for using AI in hiring processes?",
    "How can organizations ensure data quality for AI readiness?",
    "Explain 'Adversarial Machine Learning' and its impact on security.",
    "What are the benefits of using AI agents for compliance monitoring?",
    "How does 'Model Poisoning' differ from 'Data Poisoning'?",
    "What is a 'Risk Heat Map' and how is it used in GRC?",
    "What are the 6 pillars for AI-ready security?",
    "How does the EU AI Act impact open-source AI development?",
    "What is the significance of the AI Audit Booklet for CISA auditors?"
]

def authenticate():
    """Acquire JWT token for the benchmarker."""
    print(f"Authenticating as {ADMIN_USER}...")
    try:
        r = requests.post(f"{BASE_URL}/auth/login", json={
            "username": ADMIN_USER,
            "password": ADMIN_PASS
        }, timeout=10)
        if r.status_code == 200:
            return r.json().get("access_token")
        else:
            print(f"Auth failed: {r.text}")
            return None
    except Exception as e:
        print(f"Connection error: {e}")
        return None

def run_benchmark():
    token = authenticate()
    if not token:
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}
    results = []
    consecutive_errors = 0
    aborted_at = None
    summary = {
        "total": len(QUERIES),
        "answered": 0,
        "insufficient_data": 0,
        "error": 0,
        "total_latency": 0
    }
    
    print(f"\n🚀 Starting RAG Benchmark ({len(QUERIES)} queries, "
          f"pacing {PACING_SECONDS}s between queries)...\n")
    print(f"{'#':<3} | {'Outcome':<18} | {'Latency':<8} | {'Sources':<8}")
    print("-" * 50)
    
    for i, query in enumerate(QUERIES):
        start_time = time.time()
        outcome = "ERROR"
        latency = 0
        sources_count = 0
        answer = ""
        
        try:
            r = requests.post(f"{BASE_URL}/chat", json={"query": query}, headers=headers, timeout=60)
            latency = round(time.time() - start_time, 2)
            summary["total_latency"] += latency
            
            if r.status_code == 200:
                data = r.json()
                answer = data.get("response", "")
                sources = data.get("sources", [])
                sources_count = len(sources)
                
                # Substring check, not startswith: the model sometimes leads with a
                # preamble ("Based on the provided context:") and states
                # INSUFFICIENT_DATA later for only part of a multi-part question --
                # a strict prefix check let those slip through as false ANSWERED
                # (found 2026-08-05, present in every prior run, see
                # RAG_Benchmark_Report_v6.md and MEMORY.md).
                # Checked BEFORE the INSUFFICIENT_DATA / length branches: an engine
                # failure is neither a refusal nor an answer. /chat returns HTTP 200
                # with the error in the BODY, so status_code cannot detect it, and the
                # 44-char error string satisfied `len(answer) > 20` -- which scored 32
                # rate-limit errors as correct and produced a fake 96% on 2026-08-17.
                # See Benchmark_Scorer_Honesty_refactor.md.
                if is_engine_failure(answer):
                    outcome = "ERROR (Engine Failure)"
                    summary["error"] += 1
                elif "INSUFFICIENT_DATA" in answer:
                    outcome = "INSUFFICIENT_DATA"
                    summary["insufficient_data"] += 1
                elif len(answer) > 20:
                    outcome = "ANSWERED"
                    summary["answered"] += 1
                else:
                    outcome = "ERROR (Empty Response)"
                    summary["error"] += 1
            else:
                outcome = f"ERROR ({r.status_code})"
                summary["error"] += 1
                
        except Exception as e:
            latency = round(time.time() - start_time, 2)
            outcome = f"ERROR (Timeout/Exc)"
            summary["error"] += 1
            
        # Log to list
        results.append({
            "id": i + 1,
            "query": query,
            "outcome": outcome,
            "latency": latency,
            "sources_count": sources_count,
            "answer": answer
        })
        
        # Live feedback
        print(f"{i+1:<3} | {outcome:<18} | {latency:<8} | {sources_count:<8}")

        # Once the backend is down or the daily token budget is exhausted, every
        # remaining query fails too. Stop rather than manufacture dozens of
        # meaningless rows and a polluted archive (2026-08-17: 40 such rows).
        if outcome.startswith("ERROR"):
            consecutive_errors += 1
            if consecutive_errors >= 3:
                print(f"\n!! ABORTING after {i+1} queries -- 3 consecutive engine failures.")
                print("!! Check GET /api/v1/readiness and the backend logs (rate limit?).")
                aborted_at = i + 1
                break
        else:
            consecutive_errors = 0

        # Stay under the 8,000 TPM bucket. Skipped after the final query so pacing never
        # inflates the wall-clock of the run itself.
        if PACING_SECONDS > 0 and i < len(QUERIES) - 1:
            time.sleep(PACING_SECONDS)

    # Calculate final accuracy
    accuracy_pct = round((summary["answered"] / summary["total"]) * 100, 2)
    avg_latency = round(summary["total_latency"] / summary["total"], 2)

    summary["accuracy_percentage"] = accuracy_pct
    summary["avg_latency"] = avg_latency
    # Recorded so a future reader can tell a paced run from an unpaced one. `latency` and
    # `avg_latency` remain REQUEST latency only and exclude this sleep, so they stay
    # directly comparable with v1-v7.
    summary["pacing_seconds"] = PACING_SECONDS

    # A run containing ANY engine error is not a comparable measurement: the
    # denominator is intact but the numerator is contaminated. Flag it in the JSON so
    # a future reader cannot mistake it for a real data point.
    summary["valid"] = (summary["error"] == 0 and aborted_at is None)
    if not summary["valid"]:
        summary["invalid_reason"] = (
            f"{summary['error']} engine failure(s)"
            + (f"; aborted at query {aborted_at}/{summary['total']}" if aborted_at else "")
        )
    
    # Save to file
    final_output = {
        "summary": summary,
        "results": results
    }
    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_output, f, indent=4)
        
    print("\n" + "=" * 50)
    print(f"BENCHMARK COMPLETE")
    print(f"Accuracy: {accuracy_pct}% ({summary['answered']}/{summary['total']})")
    print(f"Avg Latency: {avg_latency}s")
    print(f"Insufficient Data: {summary['insufficient_data']}")
    print(f"System Errors: {summary['error']}")
    print(f"Full results saved to {OUTPUT_FILE}")
    print("=" * 50)

    if not summary["valid"]:
        print("!! RUN INVALID -- DO NOT QUOTE THIS ACCURACY FIGURE")
        print(f"!! {summary['invalid_reason']}")
        print("!! Engine failures are NOT answers. Re-run once the backend is healthy;")
        print("!! on Groq's free tier the daily token budget (200k TPD) allows roughly")
        print("!! one full 50-query run per day, shared with all other LLM features.")
        print(f"!! There is ALSO an 8,000 tokens/MINUTE cap. This run paced at {PACING_SECONDS}s")
        print("!! between queries. The failure SHAPE identifies which limit was hit:")
        print("!!   intermittent, with some queries recovering -> TPM. Raise the pacing and")
        print("!!   retry the same day:  GRC_BENCH_PACING=30 python backend/tests/rag_benchmark.py")
        print("!!   sustained from one query onward, no recovery -> TPD. Needs a fresh day.")
        print("!! Limits are scoped to the whole Groq ORGANIZATION -- other projects on the")
        print("!! same account spend the same budget, and there is no TPD header to check.")
        print("=" * 50)
        sys.exit(1)

if __name__ == "__main__":
    run_benchmark()
