---
name: texas-surplus-vehicles
description: >-
  Fetches the latest dynamic vehicle inventory list PDF from the Texas State Surplus Store (TFC) web portal. Bypasses Akamai protection using Chrome TLS impersonation, discovers the dynamic document link, downloads the PDF, and extracts available vehicle listings.
---

# Texas Surplus Vehicles Fetcher

## Overview
This skill automatically scrapes the Texas Facilities Commission (TFC) State Surplus Store storefront (`https://web.tfc.texas.gov/public/state-surplus-store`), locates the dynamic link for the `"list of vehicles for sale at the State Surplus Store"`, and downloads the latest vehicle inventory PDF.

## Usage

### Run Python Script Directly
```bash
./venv/bin/python3 src/pull_surplus_vehicles.py [output_path.pdf]
```

## Workflow Steps

1. **Access Storefront**: Send HTTP GET request to `https://web.tfc.texas.gov/public/state-surplus-store` using `curl_cffi` with Chrome browser TLS impersonation to bypass Akamai WAF blocking (HTTP 403).
2. **Find Dynamic Link**: Parse the HTML DOM for an `<a>` tag matching text `"list of vehicles for sale at the State Surplus Store"`.
3. **Download PDF**: Request the resolved document URL (`https://web.tfc.texas.gov/home/showpublisheddocument/...`) and save the response stream directly as a PDF file.
4. **Summary & Verification**: Parse page count and asset details using `PyMuPDF` (`fitz`).

## Dependencies
- `curl_cffi` (for Akamai TLS fingerprint bypass)
- `beautifulsoup4` (HTML parsing)
- `pymupdf` (PDF text inspection)
