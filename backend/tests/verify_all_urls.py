import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

urls = {
    "NIST CSF 2.0": "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
    "NIST SP 800-161r1 (TPRM)": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-161r1.pdf",
    "NIST AI 600-1 (GenAI Profile)": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf",
    "NIST AI 100-2 (Adversarial ML)": "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-2e2025.pdf",
    "OWASP Top 10 LLM Applications": "https://github.com/OWASP/www-project-top-10-for-large-language-model-applications/raw/main/assets/PDF/OWASP-Top-10-for-LLMs-2023-v1_1.pdf",
    "EU AI Act (Consilium)": "https://data.consilium.europa.eu/doc/document/ST-5662-2024-INIT/en/pdf",
    "GDPR (Consilium)": "https://data.consilium.europa.eu/doc/document/ST-5419-2016-INIT/en/pdf"
}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def main():
    print("Verifying official GRC source document URLs...\n")
    all_ok = True
    for name, url in urls.items():
        try:
            r = requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=20, verify=True)
            status = r.status_code
            content_type = r.headers.get("content-type", "unknown")
            content_length = r.headers.get("content-length", "unknown")
            
            # Read first 10 bytes to verify PDF header
            first_bytes = r.raw.read(10)
            
            print(f"{name}:")
            print(f"  URL: {url}")
            print(f"  Status: {status}")
            print(f"  Content-Type: {content_type}")
            print(f"  Content-Length: {content_length} bytes")
            print(f"  Header bytes: {first_bytes}")
            
            is_pdf = b"%PDF" in first_bytes or "pdf" in content_type.lower()
            if status == 200 and is_pdf:
                print("  Verdict: VERIFIED (Status 200, PDF Header OK)")
            else:
                print("  Verdict: FAILED / WARNING (Not a verified PDF or non-200 status)")
                all_ok = False
        except Exception as e:
            print(f"{name}:")
            print(f"  URL: {url}")
            print(f"  Error: {e}")
            print("  Verdict: FAILED")
            all_ok = False
        print("-" * 60)
        
    if all_ok:
        print("\nAll 7 source URLs are verified and responsive.")
    else:
        print("\nSome URLs failed verification. Please review the errors.")

if __name__ == "__main__":
    main()
