import os
import json
import hashlib
import time
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional
from core.config import settings
from core.logger import logger
from core.database import audit_logger
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_core.prompts import ChatPromptTemplate

PRODUCTION_PROMPT_TEMPLATE = """You are a senior GRC (Governance, Risk, and Compliance) Auditor.
Answer the following question explicitly and ONLY based on the provided context.
- If the answer is not in the context, state: "INSUFFICIENT_DATA: The provided compliance frameworks do not contain this information."
- Do not cite outside knowledge or invent controls.
- Maintain a professional, technical, and objective tone.

Context:
{context}

Question: {question}

Auditor Response:"""

GOLDEN_MAPPINGS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "golden_mappings.json")
GOLDEN_MATCH_THRESHOLD = 0.70  # empirically derived, see Golden_Mapping_refactor.md


@dataclass
class IngestionState:
    """Tracks the lifecycle of an ingestion job."""
    status: str = "idle"  # idle | running | completed | failed
    total_files: int = 0
    processed_files: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    split_count: int = 0

    @property
    def elapsed_seconds(self) -> float:
        if self.start_time is None:
            return 0.0
        end = self.end_time or time.time()
        return round(end - self.start_time, 2)

    @property
    def progress_pct(self) -> int:
        if self.total_files == 0:
            return 0
        return int((self.processed_files / self.total_files) * 100)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "progress_pct": self.progress_pct,
            "errors": self.errors,
            "elapsed_seconds": self.elapsed_seconds,
            "split_count": self.split_count,
        }

class RAGEngine:
    def __init__(self, documents_path: str = None):
        self.documents_path = documents_path or settings.DOCUMENTS_PATH
        self.vector_store = None
        self.qa_chain = None
        self.api_key = settings.GOOGLE_API_KEY
        self.ingestion_state = IngestionState()
        self.reranker = None  # lazy-loaded cross-encoder (Change 3)
        self.embeddings = None  # lazy-loaded, cached HuggingFaceEmbeddings for golden-mapping matching
        self.golden_mappings = None       # lazy-loaded list of golden mapping entries
        self.golden_trigger_vecs = None   # list[np.ndarray], one L2-normalized matrix per entry
        if not self.api_key:
            logger.warn("GOOGLE_API_KEY not found. RAG will not work until set.")

    def get_ingestion_status(self) -> dict:
        """Return the current ingestion state as a dict."""
        return self.ingestion_state.to_dict()

    def ingest_documents(self):
        """
        Reads PDFs from GRC_Analyst and embeds them into FAISS using Gemini Embeddings.
        """
        logger.info(f"Scanning {self.documents_path} for PDFs...")
        
        if not self.api_key:
            return {"status": "error", "message": "Missing GOOGLE_API_KEY"}

        try:
            # Load PDFs
            loader = DirectoryLoader(self.documents_path, glob="**/*.pdf", loader_cls=PyPDFLoader)
            documents = loader.load()
            logger.info(f"Loaded {len(documents)} PDF document chunks.")
            
            return self._process_documents(documents)
        except Exception as e:
            logger.error(f"Error ingesting PDFs: {str(e)}")
            return {"status": "error", "message": str(e)}

    def ingest_notes(self, notes_path: str):
        """
        Reads Markdown/Text files from the notebooks directory.
        """
        logger.info(f"Scanning {notes_path} for Notes...")
        
        if not self.api_key:
            return {"status": "error", "message": "Missing GOOGLE_API_KEY"}

        try:
            from langchain_community.document_loaders import TextLoader
            # Load Markdown & Text
            loader_md = DirectoryLoader(notes_path, glob="**/*.md", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
            loader_txt = DirectoryLoader(notes_path, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
            
            documents = loader_md.load() + loader_txt.load()
            logger.info(f"Loaded {len(documents)} Note document chunks.")
            
            return self._process_documents(documents)
        except Exception as e:
            logger.error(f"Error ingesting Notes: {str(e)}")
            return {"status": "error", "message": str(e)}

    async def initialize_index(self, glob: str = "*.pdf"):
        """Builds or loads the vector store with progress tracking."""
        if not self.api_key:
            logger.error("RAG Initialization failed: Missing API Key")
            return
        
        self.ingestion_state = IngestionState(status="running", start_time=time.time())
        logger.info("RAG Indexing started", path=self.documents_path, pattern=glob)
        try:
            import fnmatch
            docs = []
            files = [f for f in os.listdir(self.documents_path) if fnmatch.fnmatch(f.lower(), glob.lower())]
            self.ingestion_state.total_files = len(files)
            
            for i, file_name in enumerate(files):
                file_path = os.path.join(self.documents_path, file_name)
                try:
                    loader = PyPDFLoader(file_path)
                    file_docs = loader.load()
                    docs.extend(file_docs)
                    
                    # Record chain-of-custody
                    with open(file_path, "rb") as fh:
                        file_hash = hashlib.sha256(fh.read()).hexdigest()
                    file_size = os.path.getsize(file_path)
                    audit_logger.log_evidence(file_name, file_hash, file_size, file_path)
                except Exception as file_error:
                    error_msg = f"{file_name}: {str(file_error)}"
                    self.ingestion_state.errors.append(error_msg)
                    logger.warn("RAG Indexing: Skipping corrupted file", file=file_name, error=str(file_error))
                finally:
                    self.ingestion_state.processed_files = i + 1

            if not docs:
                logger.warn("RAG Indexing: No valid PDF documents found in path", path=self.documents_path)
                self.ingestion_state.status = "completed"
                self.ingestion_state.end_time = time.time()
                return

            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
            splits = text_splitter.split_documents(docs)
            self.ingestion_state.split_count = len(splits)

            # all-MiniLM-L6-v2 is a lightweight, high-performance local standard (Phase C Pivot)
            embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self.vector_store = FAISS.from_documents(splits, embeddings)
            
            # Persist to avoid re-indexing
            self.vector_store.save_local("faiss_index")
            self._save_index_hash("faiss_index")
            self._init_chain()
            
            self.ingestion_state.status = "completed"
            self.ingestion_state.end_time = time.time()
            logger.info("RAG Indexing completed", doc_count=len(docs), split_count=len(splits),
                        elapsed=self.ingestion_state.elapsed_seconds)
        except Exception as e:
            self.ingestion_state.status = "failed"
            self.ingestion_state.errors.append(str(e))
            self.ingestion_state.end_time = time.time()
            logger.error("RAG Indexing total failure", error=str(e))

    def _process_documents(self, documents):
        if not documents:
            return {"status": "warning", "message": "No documents found to ingest."}

        # Split Text
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        texts = text_splitter.split_documents(documents)
        
        # Create Local Embeddings (Phase C Pivot)
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # Merge with existing index if possible, otherwise create new
        if os.path.exists("faiss_index"):
             old_db = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
             self.vector_store = FAISS.from_documents(texts, embeddings)
             self.vector_store.merge_from(old_db)
        else:
            self.vector_store = FAISS.from_documents(texts, embeddings)
        
        # Persist locally
        self.vector_store.save_local("faiss_index")
        self._save_index_hash("faiss_index")
        
        self._init_chain()
        
        return {"status": "success", "count": len(texts)}

    def _hash_index(self, path="faiss_index"):
        """Generate SHA-256 hash of the FAISS index files for integrity verification."""
        h = hashlib.sha256()
        if not os.path.exists(path):
            return None
        for fname in sorted(os.listdir(path)):
            if fname == ".integrity":
                continue
            filepath = os.path.join(path, fname)
            if os.path.isfile(filepath):
                with open(filepath, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
        return h.hexdigest()

    def _save_index_hash(self, path="faiss_index"):
        """Save the current index hash to a manifest file."""
        index_hash = self._hash_index(path)
        if index_hash:
            manifest_path = os.path.join(path, ".integrity")
            with open(manifest_path, "w") as f:
                f.write(index_hash)
            logger.info("RAG: Index manifest signed with integrity hash", path=manifest_path)

    def _verify_index_hash(self, path="faiss_index"):
        """Verify the FAISS index has not been tampered with."""
        manifest_path = os.path.join(path, ".integrity")
        if not os.path.exists(manifest_path):
            logger.warn("FAISS integrity: No manifest found, skipping verification")
            return True  # No manifest = first load, allow it
        
        with open(manifest_path, "r") as f:
            stored_hash = f.read().strip()
        
        # Hash all files EXCEPT the manifest itself
        h = hashlib.sha256()
        for fname in sorted(os.listdir(path)):
            if fname == ".integrity":
                continue
            filepath = os.path.join(path, fname)
            if os.path.isfile(filepath):
                with open(filepath, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
        
        current_hash = h.hexdigest()
        if current_hash != stored_hash:
            logger.error("FAISS integrity: INDEX TAMPERED WITH", stored=stored_hash[:16], current=current_hash[:16])
            return False
        
        logger.info("FAISS integrity: Verified OK")
        return True

    def _get_embeddings(self):
        """Lazily instantiate and cache the shared embedding model."""
        if self.embeddings is None:
            self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        return self.embeddings

    def _load_golden_mappings(self):
        """Load and embed the hand-curated Golden Mapping entries (see
        Golden_Mapping_refactor.md). Each entry's trigger_phrases are embedded
        once and cached; matched at query time against the live question."""
        with open(GOLDEN_MAPPINGS_PATH, "r", encoding="utf-8") as f:
            self.golden_mappings = json.load(f)

        embeddings = self._get_embeddings()
        self.golden_trigger_vecs = []
        for entry in self.golden_mappings:
            vecs = np.array(embeddings.embed_documents(entry["trigger_phrases"]))
            vecs = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
            self.golden_trigger_vecs.append(vecs)

    def _match_golden_mappings(self, text: str) -> list:
        """Return golden mapping entries whose trigger phrases are close
        enough (cosine similarity) to the incoming question to bypass fuzzy
        vector retrieval for known compliance identifiers/topics."""
        if self.golden_mappings is None:
            self._load_golden_mappings()
        if not self.golden_mappings:
            return []

        embeddings = self._get_embeddings()
        q_vec = np.array(embeddings.embed_query(text))
        q_vec = q_vec / np.linalg.norm(q_vec)

        hits = []
        for entry, trig_vecs in zip(self.golden_mappings, self.golden_trigger_vecs):
            sim = float((trig_vecs @ q_vec).max())
            if sim >= GOLDEN_MATCH_THRESHOLD:
                hits.append((sim, entry))
        hits.sort(key=lambda p: -p[0])
        return [entry for _, entry in hits]

    def _init_chain(self):
        """
        Initializes the LCEL Chain (Prompt | LLM | Parser).
        Retrieval is now handled explicitly in query() to capture sources.
        """
        prompt = ChatPromptTemplate.from_template(PRODUCTION_PROMPT_TEMPLATE)
        model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=self.api_key)

        self.qa_chain = (
            prompt
            | model
            | StrOutputParser()
        )

    async def query(self, text: str):
        """
        Retrieves context and generates an answer, returning sources.
        """
        if not self.vector_store:
            if os.path.exists("faiss_index") and self.api_key:
                if not self._verify_index_hash("faiss_index"):
                    return {"answer": "SECURITY ALERT: Knowledge base integrity check failed. Contact administrator.", "sources": []}
                embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
                try:
                    self.vector_store = FAISS.load_local("faiss_index", embeddings, allow_dangerous_deserialization=True)
                    self._init_chain()
                except Exception as e:
                    return {"answer": f"Error loading index: {str(e)}", "sources": []}
            else:
                return {"answer": "RAG Engine not initialized. Please ingest documents first.", "sources": []}
        
        # 1. Explicit Retrieval (wide bi-encoder recall, cross-encoder precision)
        try:
            # 0. Golden Mapping check — known compliance identifiers/topics that
            # bypass fuzzy retrieval via a hand-curated, source-cited context block
            golden_hits = self._match_golden_mappings(text)

            # Similarity search is currently synchronous in FAISS-cpu
            candidates = self.vector_store.similarity_search(text, k=20)
            if self.reranker is None:
                from sentence_transformers import CrossEncoder
                self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            scores = self.reranker.predict([(text, d.page_content) for d in candidates])
            ranked = sorted(zip(scores, candidates), key=lambda p: p[0], reverse=True)
            docs = [d for _, d in ranked[:10]]
            context_text = "\n\n".join([d.page_content for d in docs])

            if golden_hits:
                golden_block = "\n\n".join(
                    f"[{h['framework']} — verified reference] {h['canonical_context']}"
                    for h in golden_hits
                )
                context_text = golden_block + "\n\n" + context_text

            # 2. Extract Sources
            sources = list(set([os.path.basename(d.metadata.get('source', 'unknown')) for d in docs]))
            for h in golden_hits:
                if h["source_file"] not in sources:
                    sources.append(h["source_file"])

            # 3. Generate Answer
            answer = await self.qa_chain.ainvoke({"context": context_text, "question": text})
            
            return {
                "answer": answer,
                "sources": sources,
                "context": context_text
            }
        except Exception as e:
            logger.error("RAG Query Error", error=str(e))
            return {"answer": "I encountered an error processing your request.", "sources": []}

# Singleton instance
rag_engine = RAGEngine()
