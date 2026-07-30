import os
import shutil
import hashlib

def get_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def make_readonly(path):
    # Set read-only attribute
    os.chmod(path, 0o444)

def main():
    workspace_dir = r"C:\Users\efosb\OneDrive\Desktop\GRC Inspector"
    source_analyst = os.path.join(workspace_dir, "GRC_Analyst")
    source_faiss = os.path.join(workspace_dir, "GRC_Command_Center", "faiss_index")
    
    snapshot_dir = os.path.join(workspace_dir, "corpus_v1_snapshot")
    snap_analyst = os.path.join(snapshot_dir, "GRC_Analyst")
    snap_faiss = os.path.join(snapshot_dir, "faiss_index")
    
    print("Starting snapshot creation...")
    
    # Create directories
    os.makedirs(snap_analyst, exist_ok=True)
    os.makedirs(snap_faiss, exist_ok=True)
    
    # 1. Copy GRC_Analyst files
    print("\nCopying GRC_Analyst PDFs...")
    pdf_count = 0
    for file in os.listdir(source_analyst):
        if file.lower().endswith(".pdf"):
            src_file = os.path.join(source_analyst, file)
            dst_file = os.path.join(snap_analyst, file)
            shutil.copy2(src_file, dst_file)
            
            # Verify bit-exact
            src_hash = get_sha256(src_file)
            dst_hash = get_sha256(dst_file)
            if src_hash != dst_hash:
                raise Exception(f"Hash mismatch for {file}!")
                
            make_readonly(dst_file)
            pdf_count += 1
            
    print(f"Successfully copied and verified {pdf_count} PDFs.")
    
    # 2. Copy faiss_index files
    print("\nCopying faiss_index files...")
    faiss_count = 0
    for file in os.listdir(source_faiss):
        src_file = os.path.join(source_faiss, file)
        if os.path.isfile(src_file):
            dst_file = os.path.join(snap_faiss, file)
            shutil.copy2(src_file, dst_file)
            
            # Verify bit-exact
            src_hash = get_sha256(src_file)
            dst_hash = get_sha256(dst_file)
            if src_hash != dst_hash:
                raise Exception(f"Hash mismatch for {file}!")
                
            make_readonly(dst_file)
            faiss_count += 1
            
    print(f"Successfully copied and verified {faiss_count} index files.")
    print("\nSnapshot v1 created and verified as bit-exact!")

if __name__ == "__main__":
    main()
