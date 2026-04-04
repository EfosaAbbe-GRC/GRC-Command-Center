import json
import os
from core.logger import logger

class DataService:
    def __init__(self):
        self.fixtures_path = os.path.join(os.path.dirname(__file__), "data", "fixtures.json")
        self._load_data()

    def _load_data(self):
        try:
            if os.path.exists(self.fixtures_path):
                with open(self.fixtures_path, 'r') as f:
                    data = json.load(f)
                    self.cached_policies = data.get("policies", [])
                    self.cached_jobs = data.get("jobs", [])
                    self.cached_kpis = data.get("kpis", {})
                    self.cached_dashboard = data.get("dashboard", {})
                    self.cached_frameworks = data.get("framework_mappings", {})
                logger.info("Data fixtures loaded successfully")
            else:
                logger.warn("Data fixtures not found, using empty defaults")
                self.cached_policies = []
                self.cached_jobs = []
                self.cached_kpis = {}
                self.cached_dashboard = {}
                self.cached_frameworks = {}
        except Exception as e:
            logger.error("Failed to load data fixtures", error=str(e))
            self.cached_policies = []
            self.cached_jobs = []
            self.cached_kpis = {}
            self.cached_dashboard = {}
            self.cached_frameworks = {}

    def get_compliance_policies(self):
        return self.cached_policies

    def get_ops_jobs(self):
        return self.cached_jobs

    def get_executive_kpis(self):
        return self.cached_kpis

    def get_dashboard_stats(self):
        return self.cached_dashboard

    def get_framework_mappings(self, policy_id: str = None):
        """Return framework mappings, optionally filtered by policy ID."""
        if policy_id:
            mapping = self.cached_frameworks.get(policy_id, {})
            return mapping.get("frameworks", [])
        return self.cached_frameworks

    def get_knowledge_documents(self):
        """Scan the documents directory and return metadata about indexed files."""
        from core.config import settings
        import hashlib
        
        docs = []
        doc_path = settings.DOCUMENTS_PATH
        
        if not os.path.exists(doc_path):
            return docs
        
        # Check which files are in the FAISS index
        index_exists = os.path.exists("faiss_index")
        
        for i, fname in enumerate(sorted(os.listdir(doc_path))):
            filepath = os.path.join(doc_path, fname)
            if not os.path.isfile(filepath):
                continue
            
            # Determine type from extension
            ext = os.path.splitext(fname)[1].lower()
            type_map = {'.pdf': 'PDF', '.json': 'JSON', '.xlsx': 'XLSX', '.docx': 'DOCX', '.csv': 'CSV', '.md': 'MD', '.txt': 'TXT'}
            file_type = type_map.get(ext, 'OTHER')
            
            # Get file size
            size_bytes = os.path.getsize(filepath)
            if size_bytes >= 1024 * 1024:
                size_str = f"{size_bytes / (1024*1024):.1f} MB"
            else:
                size_str = f"{size_bytes / 1024:.0f} KB"
            
            # Get modification time
            import time
            mod_time = os.path.getmtime(filepath)
            mod_str = time.strftime("%Y-%m-%d", time.localtime(mod_time))
            
            # Determine index status
            if ext == '.pdf' and index_exists:
                status = "INDEXED"
            elif ext == '.pdf':
                status = "PENDING"
            else:
                status = "UNSUPPORTED"
            
            docs.append({
                "id": f"doc_{i+1}",
                "name": fname,
                "type": file_type,
                "size": size_str,
                "indexed": mod_str,
                "status": status,
            })
        
        return docs

# Singleton instance
data_service = DataService()
