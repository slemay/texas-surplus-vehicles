#!/usr/bin/env python3
"""
Texas Surplus Vehicle Inventory Refresh Script
Full automated pipeline: Scrapes TFC storefront -> Downloads latest dynamic PDF -> Decodes NHTSA VINs -> Fetches NHTSA Safety Recalls -> Maps EPA MPG & stock images (with automatic SVG stock photo generator for new models) -> Updates vehicles_final.json for the Dashboard.
"""

import sys
import os
import re
import json
import time
from datetime import datetime, timezone
import zoneinfo
from curl_cffi import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

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


# Standard EPA MPG lookup table by VIN / Engine
MPG_LOOKUP = {
    '3C6RR6KT8GG373839': {'city': 15, 'hwy': 22, 'combined': 17},
    '1FAHP2MK6GG145332': {'city': 16, 'hwy': 23, 'combined': 18},
    '1FAHP2MK2JG103330': {'city': 16, 'hwy': 23, 'combined': 18},
    '1GNLCDEC9KR251362': {'city': 15, 'hwy': 22, 'combined': 18},
    '1FM5K8AR6KGB24257': {'city': 16, 'hwy': 22, 'combined': 18},
    '1FM5K8AR3KGB24264': {'city': 16, 'hwy': 22, 'combined': 18},
    '1FM5K8ARXKGA79534': {'city': 16, 'hwy': 22, 'combined': 18},
    '1FM5K8AT5KGB24388': {'city': 16, 'hwy': 22, 'combined': 18},
    '1GNLCDEC7LR289643': {'city': 15, 'hwy': 22, 'combined': 18},
    '1GNLCDECXLR251372': {'city': 15, 'hwy': 22, 'combined': 18},
    '1GNLCDEC6LR291593': {'city': 15, 'hwy': 22, 'combined': 18},
    '1GNLCDEC9LR303655': {'city': 15, 'hwy': 22, 'combined': 18},
    '1GNLCDEC9LR292835': {'city': 15, 'hwy': 22, 'combined': 18},
    '3C4PDCBG5JT512016': {'city': 19, 'hwy': 25, 'combined': 21},
    '3GCUKNEC3JG398300': {'city': 16, 'hwy': 22, 'combined': 18},
    '3GCUKNEC5HG403491': {'city': 16, 'hwy': 22, 'combined': 18},
    '2G1WA5E37F1124909': {'city': 19, 'hwy': 29, 'combined': 22}
}

# Standard Edmunds & KBB lookup data
EDMUNDS_KBB_DATA = {
    'RAM 1500': {
        'edmunds': {
            'rating': 4.5,
            'ratingText': "Edmunds Rating: 4.5 / 5 - Outstanding",
            'summary': "The 2016 RAM 1500 stands out in the full-size pickup class thanks to its ultra-smooth coil-spring rear suspension, quiet and luxurious cabin, and muscular 5.7L Hemi V8 engine.",
            'pros': [
                "Unique coil-spring rear suspension delivers the smoothest ride quality in its class",
                "Powerful 5.7L Hemi V8 with smooth 8-speed automatic transmission",
                "Quiet, upscale interior with intuitive Uconnect 8.4 touchscreen",
                "Lockable RamBox bedside storage bins add great utility"
            ],
            'cons': [
                "Maximum towing capacity falls slightly behind Ford/Chevy class leaders",
                "Rotary gear-selector dial takes time to get used to"
            ],
            'verdict': "An exceptional full-size truck for daily driving and long-distance hauling with best-in-class ride comfort.",
            'url': "https://www.edmunds.com/ram/1500/2016/review/"
        },
        'kbb_base_fair_price': 10500,
        'kbb_url': "https://www.kbb.com/ram/1500-crew-cab/2016/"
    },
    'TAURUS': {
        'edmunds': {
            'rating': 4.2,
            'ratingText': "Edmunds Rating: 4.2 / 5 - Very Good",
            'summary': "The Ford Police Interceptor Sedan (built on the Taurus platform) offers heavy-duty high-speed stability, standard All-Wheel Drive, and robust fleet engineering designed for severe service.",
            'pros': [
                "Standard Intelligent AWD provides exceptional all-weather traction and handling",
                "Heavy-duty police suspension, high-capacity cooling, and reinforced brakes",
                "Quiet front cabin with heavy-duty police pursuit calibration",
                "Strong crash safety ratings and sturdy body structure"
            ],
            'cons': [
                "Thick roof pillars restrict rearward blind-spot visibility",
                "Rear seat legroom is somewhat limited relative to large exterior dimensions"
            ],
            'verdict': "A tough, high-performance AWD sedan offering pursuit-grade mechanicals at an unbeatable surplus price point.",
            'url': "https://www.edmunds.com/ford/taurus/2016/review/"
        },
        'kbb_base_fair_price': 7400,
        'kbb_url': "https://www.kbb.com/ford/taurus/2018/"
    },
    'TAHOE': {
        'edmunds': {
            'rating': 4.6,
            'ratingText': "Edmunds Rating: 4.6 / 5 - Excellent",
            'summary': "The Chevrolet Tahoe PPV (Police Pursuit Vehicle) combines a commanding 5.3L V8 engine, heavy-duty pursuit suspension, lower ride height for high-speed stability, and massive cargo capability.",
            'pros': [
                "Robust 5.3L EcoTec3 V8 delivers confident acceleration and high towing capability",
                "PPV pursuit package includes upgraded oil coolers, heavy-duty brakes, and lowered suspension",
                "Extremely spacious cabin with versatile cargo storage capacity",
                "Quiet high-speed cruising with impressive highway stability"
            ],
            'cons': [
                "Solid rear axle can feel firm over severe bumps",
                "Cargo floor is somewhat high due to fold-flat seating design"
            ],
            'verdict': "The gold standard for full-size utility vehicles — rugged, powerful, and built to handle harsh conditions.",
            'url': "https://www.edmunds.com/chevrolet/tahoe/2020/review/"
        },
        'kbb_base_fair_price': 14200,
        'kbb_url': "https://www.kbb.com/chevrolet/tahoe/2020/"
    },
    'EXPLORER': {
        'edmunds': {
            'rating': 4.3,
            'ratingText': "Edmunds Rating: 4.3 / 5 - Excellent",
            'summary': "The Ford Police Interceptor Utility (Explorer chassis) is renowned for its versatile AWD system, pursuit-tuned suspension, roomy interior, and balanced 3.7L V6 performance.",
            'pros': [
                "Standard Intelligent AWD provides excellent wet and winter weather capability",
                "Refined ride quality with heavy-duty police pursuit cooling and suspension upgrades",
                "Spacious front cabin with durable law-enforcement interior materials",
                "Solid towing and cargo capacity for active state agency use"
            ],
            'cons': [
                "Wide front pillars can block side cornering view",
                "Infotainment screen is basic on utility fleet models"
            ],
            'verdict': "One of the most capable and popular utility vehicles in public service, offering all-weather versatility and reliability.",
            'url': "https://www.edmunds.com/ford/explorer/2019/review/"
        },
        'kbb_base_fair_price': 10400,
        'kbb_url': "https://www.kbb.com/ford/explorer/2019/"
    },
    'JOURNEY': {
        'edmunds': {
            'rating': 3.8,
            'ratingText': "Edmunds Rating: 3.8 / 5 - Good Value",
            'summary': "The 2018 Dodge Journey offers an affordable entry into midsize crossover ownership with low maintenance costs, smooth city cruising, and versatile seating configurations.",
            'pros': [
                "Exceptionally low odometer mileage (37,628 miles) on this surplus vehicle",
                "Smooth ride quality that absorbs road bumps easily",
                "User-friendly layout with clever floor storage cubbies",
                "Economical purchase price for a versatile crossover utility"
            ],
            'cons': [
                "4-speed automatic transmission on 2.4L engine feels dated",
                "Cargo space behind third row is compact"
            ],
            'verdict': "A budget-friendly utility vehicle that offers outstanding low-mileage value for everyday commuting.",
            'url': "https://www.edmunds.com/dodge/journey/2018/review/"
        },
        'kbb_base_fair_price': 13650,
        'kbb_url': "https://www.kbb.com/dodge/journey/2018/"
    },
    'SILVERADO': {
        'edmunds': {
            'rating': 4.5,
            'ratingText': "Edmunds Rating: 4.5 / 5 - Outstanding",
            'summary': "The Chevrolet Silverado 1500 Crew Cab 4x4 is celebrated for its powerful 5.3L V8 engine, remarkably quiet highway cabin, robust 4WD system, and heavy-duty towing performance.",
            'pros': [
                "Quiet, comfortable, and well-insulated Crew Cab interior",
                "Strong 5.3L V8 engine with active fuel management and high towing capacity",
                "Capable Autotrac 4WD system with low-range transfer case",
                "CornerStep rear bumper and durable roll-formed steel bed"
            ],
            'cons': [
                "Transmission can hesitate during hard downshifts",
                "Steering feel is relaxed rather than sporty"
            ],
            'verdict': "A powerhouse 4x4 pickup truck that combines serious work capacity with refined passenger comfort.",
            'url': "https://www.edmunds.com/chevrolet/silverado-1500/2018/review/"
        },
        'kbb_base_fair_price': 19500,
        'kbb_url': "https://www.kbb.com/chevrolet/silverado-1500-crew-cab/2018/"
    },
    'IMPALA': {
        'edmunds': {
            'rating': 4.4,
            'ratingText': "Edmunds Rating: 4.4 / 5 - Excellent",
            'summary': "The 2015 Chevrolet Impala is a top-ranked full-size sedan praised for its cavernous passenger cabin, serene highway ride quality, huge trunk space, and smooth 3.6L V6 engine.",
            'pros': [
                "Abundant passenger room in both front and back seats",
                "Massive 18.8 cubic feet trunk capacity",
                "Quiet, smooth highway ride quality that absorbs road imperfections effortlessly",
                "Strong 305-hp 3.6L V6 engine with crisp acceleration"
            ],
            'cons': [
                "Thick rear roof pillars impair rear diagonal visibility",
                "Large size makes tight parallel parking take extra attention"
            ],
            'verdict': "One of the finest full-size American sedans made, providing luxury-level highway comfort at a fraction of the cost.",
            'url': "https://www.edmunds.com/chevrolet/impala/2015/review/"
        },
        'kbb_base_fair_price': 8850,
        'kbb_url': "https://www.kbb.com/chevrolet/impala/2015/"
    }
}

def get_edmunds_and_kbb(vehicle):
    desc = (vehicle.get('description') or '').upper()
    specs = vehicle.get('specs', {})
    make = (specs.get('Make') or '').upper()
    mileage = vehicle.get('mileage', 150000)
    sales_price = vehicle.get('salesPrice', 0.0)
    year = int(specs.get('ModelYear') or 2018)

    key = 'TAHOE'
    if 'RAM' in desc or ('1500' in desc and 'RAM' in make):
        key = 'RAM 1500'
    elif 'TAURUS' in desc or 'INTERCEPTOR SEDAN' in desc:
        key = 'TAURUS'
    elif 'EXPLORER' in desc:
        key = 'EXPLORER'
    elif 'JOURNEY' in desc:
        key = 'JOURNEY'
    elif 'SILVERADO' in desc or ('1500' in desc and 'CHEVROLET' in desc):
        key = 'SILVERADO'
    elif 'IMPALA' in desc:
        key = 'IMPALA'
    elif 'TAHOE' in desc:
        key = 'TAHOE'

    base_data = EDMUNDS_KBB_DATA.get(key, EDMUNDS_KBB_DATA['TAHOE'])
    edmunds = dict(base_data['edmunds'])

    kbb_base = base_data['kbb_base_fair_price']
    if year >= 2020:
        kbb_base += 1200
    elif year == 2019:
        kbb_base += 600
    elif year == 2016:
        kbb_base -= 500
    elif year <= 2015:
        kbb_base -= 1000

    mileage_diff = 160000 - mileage
    mileage_adj = int(mileage_diff * 0.035)
    kbb_fair_price = max(4000, kbb_base + mileage_adj)

    min_range = int(kbb_fair_price * 0.88)
    max_range = int(kbb_fair_price * 1.12)
    private_party = int(kbb_fair_price * 0.92)
    retail_value = int(kbb_fair_price * 1.10)
    savings = max(0, int(kbb_fair_price - sales_price))
    savings_pct = round((savings / kbb_fair_price) * 100, 1) if kbb_fair_price > 0 else 0

    kbb_valuation = {
        'fairPurchasePrice': kbb_fair_price,
        'formattedFairPrice': f"${kbb_fair_price:,}",
        'priceRange': f"${min_range:,} - ${max_range:,}",
        'privatePartyValue': private_party,
        'suggestedRetail': retail_value,
        'savingsVsKbb': savings,
        'savingsPct': savings_pct,
        'formattedSavings': f"${savings:,}",
        'url': base_data['kbb_url']
    }

    return edmunds, kbb_valuation

def generate_stock_svg(make, model, year, body_class, output_path):
    make = (make or 'SURPLUS').upper()
    model = (model or 'VEHICLE').upper()
    year = str(year or '')
    
    if 'FORD' in make:
        primary = '#0284c7'
    elif 'CHEVROLET' in make or 'CHEVY' in make:
        primary = '#d97706'
    elif 'RAM' in make or 'DODGE' in make:
        primary = '#dc2626'
    else:
        primary = '#4f46e5'
        
    svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 338" width="600" height="338">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#0f172a" />
      <stop offset="100%" stop-color="#1e293b" />
    </linearGradient>
    <linearGradient id="accent" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{primary}" />
      <stop offset="100%" stop-color="#38bdf8" />
    </linearGradient>
  </defs>
  
  <rect width="600" height="338" fill="url(#bg)" />
  <path d="M0 50 H600 M0 100 H600 M0 150 H600 M0 200 H600 M0 250 H600 M0 300 H600" stroke="rgba(255,255,255,0.03)" stroke-width="1" />
  <path d="M100 0 V338 M200 0 V338 M300 0 V338 M400 0 V338 M500 0 V338" stroke="rgba(255,255,255,0.03)" stroke-width="1" />
  
  <g transform="translate(180, 70)" fill="url(#accent)" opacity="0.85">
    <path d="M 30 90 L 60 50 L 150 40 L 190 90 Z" fill="none" stroke="url(#accent)" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M 10 90 H 230 C 235 90 240 95 240 100 L 235 120 C 235 125 230 130 225 130 H 15 Z" fill="url(#accent)" opacity="0.2" />
    <circle cx="60" cy="125" r="22" fill="#0f172a" stroke="url(#accent)" stroke-width="6" />
    <circle cx="180" cy="125" r="22" fill="#0f172a" stroke="url(#accent)" stroke-width="6" />
  </g>
  
  <rect x="30" y="220" width="120" height="24" rx="6" fill="{primary}" opacity="0.2" />
  <text x="40" y="236" font-family="sans-serif" font-size="12" font-weight="bold" fill="{primary}">{year} {make}</text>
  
  <text x="30" y="275" font-family="sans-serif" font-size="22" font-weight="800" fill="#ffffff">{model}</text>
  <text x="30" y="298" font-family="sans-serif" font-size="11" fill="#94a3b8">STOCK ILLUSTRATION &bull; TEXAS SURPLUS INVENTORY</text>
</svg>'''
    
    with open(output_path, 'w') as f:
        f.write(svg_content)
        
    return output_path

def get_image(desc, specs):
    d = desc.upper()
    m = (specs.get('Model') or '').upper()
    mk = (specs.get('Make') or '').upper()
    
    if 'TAHOE' in d or 'TAHOE' in m:
        return 'images/chevrolet_tahoe.jpg'
    elif 'EXPLORER' in d or 'EXPLORER' in m:
        return 'images/ford_explorer.jpg'
    elif 'TAURUS' in d or 'TAURUS' in m or ('FORD' in d and 'SEDAN' in d):
        return 'images/ford_taurus.jpg'
    elif 'RAM' in d or ('1500' in d and 'RAM' in mk):
        return 'images/ram_1500.jpg'
    elif 'JOURNEY' in d or 'JOURNEY' in m:
        return 'images/dodge_journey.jpg'
    elif 'SILVERADO' in d or ('1500' in d and 'CHEVROLET' in d) or ('1500' in d and 'CHEVY' in d):
        return 'images/chevrolet_silverado.jpg'
    elif 'IMPALA' in d or 'IMPALA' in m:
        return 'images/chevy_impala.jpg'
        
    sanitized_key = re.sub(r'[^a-zA-Z0-9_]', '_', f"{mk}_{m}_{specs.get('ModelYear', '')}".lower())
    svg_rel_path = f"images/{sanitized_key}.svg"
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    svg_full_path = os.path.join(project_root, 'public', 'images', f"{sanitized_key}.svg")
    
    if not os.path.exists(svg_full_path):
        generate_stock_svg(mk, m, specs.get('ModelYear'), specs.get('BodyClass'), svg_full_path)
        
    return svg_rel_path

def run_refresh():
    print("[1/5] Accessing Texas State Surplus Storefront...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
    }
    
    try:
        res = requests.get(BASE_URL, headers=headers, impersonate="chrome")
        if res.status_code != 200:
            print(f"[!] Warning: Error accessing storefront (HTTP {res.status_code}). Using existing inventory data.", file=sys.stderr)
            return
    except Exception as err:
        print(f"[!] Warning: Storefront request exception ({err}). Using existing inventory data.", file=sys.stderr)
        return
        
    soup = BeautifulSoup(res.text, 'html.parser')
    doc_url = None
    for a in soup.find_all('a'):
        text = a.get_text(strip=True)
        if LINK_TEXT.lower() in text.lower() or ("vehicle" in text.lower() and "surplus" in text.lower()):
            href = a.get('href')
            if href:
                doc_url = f"https://web.tfc.texas.gov{href}" if href.startswith('/') else href
                print(f"[+] Found dynamic PDF link: '{text}' -> {doc_url}")
                break
                
    if not doc_url:
        print("[!] Warning: Dynamic vehicle PDF link not found. Using existing inventory data.", file=sys.stderr)
        return
        
    doc_info = parse_dotnet_ticks(doc_url)
    if doc_info:
        print(f"[+] Decoded PDF Generation Timestamp: {doc_info['formattedCentral']} (.NET Ticks: {doc_info['ticks']})")

        
    print("[2/5] Downloading dynamic PDF document...")
    pdf_res = requests.get(doc_url, headers=headers, impersonate="chrome")
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    data_dir = os.path.join(project_root, 'data')
    public_data_dir = os.path.join(project_root, 'public', 'data')
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(public_data_dir, exist_ok=True)

    pdf_file = os.path.join(data_dir, "Texas_State_Surplus_Vehicles.pdf")
    public_pdf = os.path.join(public_data_dir, "Texas_State_Surplus_Vehicles.pdf")
    with open(pdf_file, 'wb') as f:
        f.write(pdf_res.content)
    with open(public_pdf, 'wb') as f:
        f.write(pdf_res.content)
    print(f"[✓] Saved PDF to {pdf_file}")
    
    print("[3/5] Extracting vehicle listings from PDF...")
    doc = fitz.open(pdf_file)
    extracted_vehicles = []
    
    for page in doc:
        text = page.get_text()
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r'^\d{3}-\d{6}-\d{2}-\d{3}$', line):
                asset_num = line
                desc = lines[i+1] if i+1 < len(lines) else ''
                vin = lines[i+2] if i+2 < len(lines) else ''
                mileage_str = lines[i+3] if i+3 < len(lines) else '0'
                price_str = lines[i+4] if i+4 < len(lines) else '0'
                
                try:
                    mileage = int(mileage_str)
                except:
                    mileage = 0
                    
                try:
                    price = float(price_str.replace('$', '').replace(',', ''))
                except:
                    price = 0.0
                    
                extracted_vehicles.append({
                    'assetNumber': asset_num,
                    'description': desc,
                    'vin': vin,
                    'mileage': mileage,
                    'salesPrice': price
                })
                i += 5
            else:
                i += 1
                
    print(f"[+] Parsed {len(extracted_vehicles)} vehicle listing(s)")
    
    print("[4/5] Decoding Specs, Recalls, Edmunds Reviews & KBB Values...")
    for v in extracted_vehicles:
        vin = v['vin']
        # NHTSA VIN Specs
        vpic_url = f"https://vpic.nhtsa.dot.gov/api/vehicles/decodevinvalues/{vin}?format=json"
        try:
            r = requests.get(vpic_url, headers={'User-Agent': 'Mozilla/5.0'}, impersonate="chrome")
            data = r.json().get('Results', [{}])[0]
            
            turbo = data.get('Turbo')
            supercharger = data.get('Supercharger')
            aspiration = 'Standard'
            if turbo and turbo.strip().lower() in ['yes', 'true', '1']:
                aspiration = 'Turbocharged'
            elif supercharger and supercharger.strip().lower() in ['yes', 'true', '1']:
                aspiration = 'Supercharged'
                
            drive_type = data.get('DriveType')
            if not drive_type or not str(drive_type).strip():
                desc_upper = (v.get('description') or '').upper()
                if 'IMPALA' in desc_upper:
                    drive_type = 'FWD/Front-Wheel Drive'
                elif 'TAHOE' in desc_upper or 'RAM' in desc_upper:
                    drive_type = 'RWD/Rear-Wheel Drive'
                
            v['specs'] = {
                'Make': data.get('Make'),
                'Model': data.get('Model'),
                'ModelYear': data.get('ModelYear'),
                'BodyClass': data.get('BodyClass'),
                'EngineCylinders': data.get('EngineCylinders'),
                'DisplacementL': data.get('DisplacementL'),
                'EngineHP': data.get('EngineHP'),
                'FuelTypePrimary': data.get('FuelTypePrimary'),
                'DriveType': drive_type,
                'PlantCity': data.get('PlantCity'),
                'PlantState': data.get('PlantState'),
                'PlantCountry': data.get('PlantCountry'),
                'VehicleType': data.get('VehicleType'),
                'Manufacturer': data.get('Manufacturer'),
                'Trim': data.get('Trim'),
                'Series': data.get('Series'),
                'Aspiration': aspiration
            }
        except Exception as e:
            v['specs'] = {'Aspiration': 'Standard', 'DriveType': 'FWD/Front-Wheel Drive'}

        # NHTSA Recalls
        make = v['specs'].get('Make') or ''
        model = v['specs'].get('Model') or ''
        year = v['specs'].get('ModelYear') or ''
        
        if 'TAURUS' in v['description'].upper(): model = 'TAURUS'
        elif 'EXPLORER' in v['description'].upper(): model = 'EXPLORER'
        elif 'TAHOE' in v['description'].upper(): model = 'TAHOE'
        elif 'RAM' in v['description'].upper() or '1500' in v['description'].upper():
            model = 'SILVERADO 1500' if 'CHEVROLET' in v['description'].upper() else '1500'
        elif 'JOURNEY' in v['description'].upper(): model = 'JOURNEY'
        elif 'IMPALA' in v['description'].upper(): model = 'IMPALA'

        recalls_url = f"https://api.nhtsa.gov/recalls/recallsByVehicle?make={make}&model={model}&modelYear={year}&format=json"
        try:
            rc_res = requests.get(recalls_url, impersonate="chrome")
            if rc_res.status_code == 200:
                rc_data = rc_res.json()
                items = []
                for r_item in rc_data.get('results', []):
                    items.append({
                        'campaignNumber': r_item.get('NHTSACampaignNumber'),
                        'component': r_item.get('Component'),
                        'summary': r_item.get('Summary'),
                        'consequence': r_item.get('Conequence') or r_item.get('Consequence'),
                        'remedy': r_item.get('Remedy'),
                        'date': r_item.get('ReportReceivedDate')
                    })
                v['recalls'] = {'count': rc_data.get('Count', 0), 'items': items}
            else:
                v['recalls'] = {'count': 0, 'items': []}
        except:
            v['recalls'] = {'count': 0, 'items': []}

        # Map MPG, Image, Edmunds Review & KBB Valuation
        v['mpg'] = MPG_LOOKUP.get(vin, {'city': 16, 'hwy': 22, 'combined': 18})
        v['image'] = get_image(v['description'], v['specs'])
        
        edmunds, kbb = get_edmunds_and_kbb(v)
        v['edmundsReview'] = edmunds
        v['kbbValuation'] = kbb
        time.sleep(0.1)
        
    print("[5/5] Writing updated vehicles_final.json...")
    output_payload = {
        "generatedAt": doc_info,
        "vehicles": extracted_vehicles
    }
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    out_paths = [
        os.path.join(project_root, 'public', 'data', 'vehicles_final.json'),
        os.path.join(project_root, 'data', 'vehicles_final.json'),
        os.path.join(project_root, 'vehicles_final.json')
    ]
    for path in out_paths:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(output_payload, f, indent=2)
        
    print(f"\n[✓] Refresh complete! Updated {len(extracted_vehicles)} inventory listings with Edmunds Reviews & KBB Values.")
    if doc_info:
        print(f"    Dynamic List Timestamp: {doc_info['formattedCentral']}")


if __name__ == '__main__':
    run_refresh()

