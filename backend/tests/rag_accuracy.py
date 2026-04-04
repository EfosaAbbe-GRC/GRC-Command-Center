import asyncio
import sys
import os

# Add backend directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from core.rag import rag_engine
from core.logger import logger

async def verify_rag():
    logger.info("AUDIT: Starting Targeted RAG Accuracy Test (ISO-42001)")
    
    # Targeting specific files for faster validation
    await rag_engine.initialize_index(glob="*42001*.pdf")
    
    questions = [
      "What is the main purpose of ISO/IEC 42001:2023?",
      "What are the core requirements for an AI Management System (AIMS)?",
      "Mention one specific control area described in Annex A of ISO 42001."
    ]
    
    print("\n" + "="*50)
    print("RAG ACCURACY VERIFICATION REPORT")
    print("="*50)
    
    for q in questions:
        print(f"\nQUERY: {q}")
        response = await rag_engine.query(q)
        answer = response.get("answer", "No Answer")
        print(f"RESPONSE: {answer[:300]}...")
        
    print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(verify_rag())
