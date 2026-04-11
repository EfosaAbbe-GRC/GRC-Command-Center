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
    summary = {
        "total": len(QUERIES),
        "answered": 0,
        "insufficient_data": 0,
        "error": 0,
        "total_latency": 0
    }
    
    print(f"\n🚀 Starting RAG Benchmark ({len(QUERIES)} queries)...\n")
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
                
                if answer.startswith("INSUFFICIENT_DATA"):
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

    # Calculate final accuracy
    accuracy_pct = round((summary["answered"] / summary["total"]) * 100, 2)
    avg_latency = round(summary["total_latency"] / summary["total"], 2)
    
    summary["accuracy_percentage"] = accuracy_pct
    summary["avg_latency"] = avg_latency
    
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

if __name__ == "__main__":
    run_benchmark()
