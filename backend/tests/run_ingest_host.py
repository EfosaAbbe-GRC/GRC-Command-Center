import os
import sys
import asyncio

# Add the backend directory to sys.path so we can import core modules
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from core.rag import rag_engine

async def main():
    print("Ingestion script imported successfully!")
    print("Documents path:", rag_engine.documents_path)
    print("API Key configured:", bool(rag_engine.api_key))

if __name__ == "__main__":
    asyncio.run(main())
