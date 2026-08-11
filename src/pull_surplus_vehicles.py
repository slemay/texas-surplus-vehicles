#!/usr/bin/env python3
"""
Texas State Surplus Store Vehicle List Fetcher
Automates fetching the current dynamic vehicle list PDF from Texas Facilities Commission (TFC).
"""

import sys
import os
import re
from datetime import datetime
from curl_cffi import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF for reading PDF text

import zoneinfo

BASE_URL = "https://web.tfc.texas.gov/public/state-surplus-store"
LINK_TEXT = "list of vehicles for sale at the State Surplus Store"

def parse_dotnet_ticks(url_or_ticks):
    ticks_str = str(url_or_ticks).rstrip('/').split('/')[-1]
    if not ticks_str.isdigit():
        match = re.search(r'\b(\d{16,20})\b', str(url_or_ticks))
        if match:
            ticks_str = match.group(1)
        else:
            return None

    ticks = int(ticks_str)
    epoch_ticks = 621355968000000000
    seconds = (ticks - epoch_ticks) / 10_000_000.0
    dt_utc = datetime.fromtimestamp(seconds, tz=timezone.utc)
    
    try:
        dt_central = dt_utc.astimezone(zoneinfo.ZoneInfo("America/Chicago"))
    except Exception:
        dt_central = dt_utc
        
    return {
        'ticks': ticks_str,
        'docUrl': str(url_or_ticks) if str(url_or_ticks).startswith('http') else f"https://web.tfc.texas.gov/home/showpublisheddocument/232/{ticks_str}",
        'isoUtc': dt_utc.isoformat(),
        'formattedCentral': dt_central.strftime('%B %d, %Y at %I:%M %p %Z'),
        'formattedShort': dt_central.strftime('%b %d, %Y, %I:%M %p'),
        'dateOnly': dt_central.strftime('%B %d, %Y')
    }

def fetch_surplus_vehicles(output_path=None):
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"Texas_State_Surplus_Vehicles_{timestamp}.pdf"
    
    print(f"[*] Accessing Texas Surplus Store storefront at: {BASE_URL}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    # Use curl_cffi with chrome TLS impersonation to bypass Akamai blocking
    res = requests.get(BASE_URL, headers=headers, impersonate="chrome", allow_redirects=True)
    if res.status_code != 200:
        print(f"[!] Error accessing storefront. Status code: {res.status_code}", file=sys.stderr)
        sys.exit(1)
        
    soup = BeautifulSoup(res.text, 'html.parser')
    vehicle_link = None
    
    for a in soup.find_all('a'):
        text = a.get_text(strip=True)
        if LINK_TEXT.lower() in text.lower() or ("vehicle" in text.lower() and "surplus" in text.lower()):
            href = a.get('href')
            if href:
                if href.startswith('/'):
                    vehicle_link = f"https://web.tfc.texas.gov{href}"
                else:
                    vehicle_link = href
                print(f"[+] Located dynamic vehicle list link: '{text}' -> {vehicle_link}")
                break
                
    if not vehicle_link:
        print(f"[!] Could not locate link labeled '{LINK_TEXT}' on page.", file=sys.stderr)
        sys.exit(1)

    doc_info = parse_dotnet_ticks(vehicle_link)
    if doc_info:
        print(f"[+] Decoded List Generation Time: {doc_info['formattedCentral']} (from .NET Ticks: {doc_info['ticks']})")

        
    print(f"[*] Downloading vehicle list PDF from {vehicle_link}...")
    doc_res = requests.get(vehicle_link, headers=headers, impersonate="chrome", allow_redirects=True)
    if doc_res.status_code != 200:
        print(f"[!] Error downloading document. Status code: {doc_res.status_code}", file=sys.stderr)
        sys.exit(1)
        
    with open(output_path, 'wb') as f:
        f.write(doc_res.content)
        
    print(f"[✓] Successfully downloaded vehicle list to: {os.path.abspath(output_path)}")
    
    # Parse PDF summary
    try:
        doc = fitz.open(output_path)
        print(f"\n--- Document Summary ({len(doc)} page(s)) ---")
        for i, page in enumerate(doc):
            text = page.get_text()
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            print(f"Page {i+1} sample ({len(lines)} lines):")
            for line in lines[:10]:
                print(f"  {line}")
    except Exception as e:
        print(f"[!] Note: PDF downloaded successfully, but could not parse text preview: {e}")
        
    return output_path

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "Texas_State_Surplus_Vehicles.pdf"
    fetch_surplus_vehicles(out_file)
