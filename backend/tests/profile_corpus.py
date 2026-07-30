import os
import sys
import json
import csv
import re
from pypdf import PdfReader

def parse_pdf_filename(chunk_id):
    # Parse PDF filename from chunk_id (e.g., "AI RMF 1.0.pdf_p7_c0" -> "AI RMF 1.0.pdf")
    # Matches everything up to .pdf or .PDF followed by _p
    match = re.match(r"^(.*?\.pdf)_p\d+_c\d+", chunk_id, re.IGNORECASE)
    if match:
        return match.group(1)
    # Fallback to general split if formatting differs
    if ".pdf_" in chunk_id.lower():
        parts = chunk_id.lower().split(".pdf_")
        return parts[0] + ".pdf"
    return chunk_id

def main():
    # Walk up three levels from backend/tests/profile_corpus.py to GRC_Command_Center
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    analyst_dir = "C:\\Users\\efosb\\OneDrive\\Desktop\\GRC Inspector\\GRC_Analyst"
    
    diagnostic_path = os.path.join(root_dir, "diagnostic_results.v1_uncalibrated.json")
    if not os.path.exists(diagnostic_path):
        print(f"Error: {diagnostic_path} not found. Cannot determine load-bearing status.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Loading uncalibrated results from: {diagnostic_path}")
    with open(diagnostic_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results", [])
    
    # Map from normalized lower case filename to (original_filename, list_of_query_ids)
    load_bearing_map = {}
    
    success_queries_count = 0
    for r in results:
        if r.get("diagnosis") == "SUCCESS":
            success_queries_count += 1
            query_id = r["query_id"]
            chunks = r.get("retrieval", {}).get("chunks", [])
            # Map top 3 chunks (or all retrieved chunks since they contributed)
            for chunk in chunks[:3]:
                chunk_id = chunk.get("chunk_id", "")
                pdf_name = parse_pdf_filename(chunk_id)
                if pdf_name:
                    pdf_key = os.path.basename(pdf_name).lower()
                    if pdf_key not in load_bearing_map:
                        load_bearing_map[pdf_key] = {"original_name": os.path.basename(pdf_name), "query_ids": []}
                    if query_id not in load_bearing_map[pdf_key]["query_ids"]:
                        load_bearing_map[pdf_key]["query_ids"].append(query_id)
                        
    print(f"Mapped {success_queries_count} successful queries. Found {len(load_bearing_map)} unique load-bearing PDFs.")
    
    # Walk the GRC_Analyst directory recursively
    print(f"Scanning directory: {analyst_dir}")
    pdf_files = []
    for root, dirs, files in os.walk(analyst_dir):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, file))
                
    print(f"Found {len(pdf_files)} PDF files to profile.")
    
    profile_records = []
    
    # Fields: Filename, FileSize_KB, PageCount, WordCount_Est, TextDensity_CharPerPage, IsLoadBearing, SupportedQueries
    for i, filepath in enumerate(pdf_files):
        filename = os.path.basename(filepath)
        pdf_key = filename.lower()
        
        file_size_kb = round(os.path.getsize(filepath) / 1024, 2)
        
        # Extract page count and text metrics using pypdf
        page_count = -1
        word_count_est = 0
        char_count = 0
        
        try:
            reader = PdfReader(filepath)
            page_count = len(reader.pages)
            
            # Read first few pages (or all if small) to estimate words/density
            text_samples = []
            for page in reader.pages:
                text = page.extract_text() or ""
                text_samples.append(text)
                
            full_text = "\n".join(text_samples)
            char_count = len(full_text)
            # Simple word estimator
            words = full_text.split()
            word_count_est = len(words)
        except Exception as e:
            print(f"Warning: Failed to read {filename} - {e}", file=sys.stderr)
            
        text_density = round(char_count / page_count, 1) if page_count > 0 else 0
        
        is_load_bearing = pdf_key in load_bearing_map
        supported_queries = []
        if is_load_bearing:
            supported_queries = sorted(load_bearing_map[pdf_key]["query_ids"])
            
        profile_records.append({
            "Filename": filename,
            "RelativePath": os.path.relpath(filepath, analyst_dir),
            "FileSize_KB": file_size_kb,
            "PageCount": page_count,
            "WordCount_Est": word_count_est,
            "TextDensity_CharPerPage": text_density,
            "IsLoadBearing": is_load_bearing,
            "SupportedQueries": ",".join(map(str, supported_queries))
        })
        
        if (i+1) % 20 == 0 or (i+1) == len(pdf_files):
            print(f"Processed {i+1}/{len(pdf_files)} PDFs...")
            
    # Output corpus_profile.csv
    profile_csv_path = os.path.join(root_dir, "corpus_profile.csv")
    print(f"Writing corpus profile to: {profile_csv_path}")
    with open(profile_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Filename", "RelativePath", "FileSize_KB", "PageCount", "WordCount_Est", "TextDensity_CharPerPage", "IsLoadBearing", "SupportedQueries"])
        writer.writeheader()
        writer.writerows(profile_records)
        
    # Output load_bearing_documents.csv
    load_bearing_csv_path = os.path.join(root_dir, "load_bearing_documents.csv")
    print(f"Writing load-bearing documents summary to: {load_bearing_csv_path}")
    with open(load_bearing_csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PDF_Filename", "Supported_Query_Count", "Supported_Query_IDs"])
        for k, v in sorted(load_bearing_map.items(), key=lambda item: len(item[1]["query_ids"]), reverse=True):
            writer.writerow([v["original_name"], len(v["query_ids"]), ",".join(map(str, sorted(v["query_ids"])))])
            
    print("\nCorpus profiling complete successfully!")

if __name__ == "__main__":
    main()
