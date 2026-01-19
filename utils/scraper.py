"""
Estonian Business Registry (e-Äriregister) Open Data Scraper
Fetches business data from official open data portal: avaandmed.ariregister.rik.ee

Data includes:
- Business name, registry code, legal form, VAT number
- Registration date, status, address
- Board members/management (CEO)
- Employee counts, revenue, profit (from annual reports)
"""

import requests
import zipfile
import io
import csv
import json
from collections import defaultdict
from typing import Optional


# Open Data Base URL
BASE_URL = "https://avaandmed.ariregister.rik.ee"

# Available datasets
DATASETS = {
    # Basic data - company names, reg codes, status, address
    "basic_csv": f"{BASE_URL}/sites/default/files/avaandmed/ettevotja_rekvisiidid__lihtandmed.csv.zip",
    # Persons on registry cards - board members, directors, etc.
    "persons_json": f"{BASE_URL}/sites/default/files/avaandmed/ettevotja_rekvisiidid__kaardile_kantud_isikud.json.zip",
    # Annual reports general data (to link report_id to registrikood)
    "reports_general": f"{BASE_URL}/sites/default/files/1.aruannete_yldandmed_kuni_31122025_0.zip",
    # Annual report elements (employees, revenue, profit)
    "reports_elements_2024": f"{BASE_URL}/sites/default/files/4.2024_aruannete_elemendid_kuni_31122025_0.zip",
    "reports_elements_2023": f"{BASE_URL}/sites/default/files/4.2023_aruannete_elemendid_kuni_31122025_0.zip",
}


def download_zip(url: str) -> bytes:
    """Download a zip file and return its content as bytes."""
    filename = url.split('/')[-1]
    print(f"  Downloading: {filename}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; Estonian Business Data Fetcher)'
    }
    
    response = requests.get(url, headers=headers, timeout=600)
    response.raise_for_status()
    
    return response.content


def extract_csv_from_zip(zip_content: bytes, delimiter: str = ';') -> list[dict]:
    """Extract and parse CSV file from zip content."""
    with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
        csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
        if not csv_files:
            raise ValueError("No CSV file found in archive")
        
        csv_filename = csv_files[0]
        print(f"    Extracting: {csv_filename}")
        
        with zf.open(csv_filename) as csvfile:
            content = csvfile.read().decode('utf-8-sig')
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
            return list(reader)


def extract_json_from_zip(zip_content: bytes) -> list[dict]:
    """Extract and parse JSON file from zip content."""
    with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
        json_files = [f for f in zf.namelist() if f.endswith('.json')]
        if not json_files:
            raise ValueError("No JSON file found in archive")
        
        json_filename = json_files[0]
        print(f"    Extracting: {json_filename}")
        
        with zf.open(json_filename) as jsonfile:
            content = jsonfile.read().decode('utf-8-sig')
            return json.loads(content)


def fetch_basic_data(limit: Optional[int] = None) -> dict[str, dict]:
    """
    Fetch basic company data with correct column mappings.
    Returns dict keyed by registry code.
    """
    zip_content = download_zip(DATASETS["basic_csv"])
    data = extract_csv_from_zip(zip_content)
    
    print(f"    Loaded {len(data)} rows")
    
    companies = {}
    for i, row in enumerate(data):
        if limit and i >= limit:
            break
        
        reg_code = row.get("ariregistri_kood", "").strip()
        if not reg_code:
            continue
        
        companies[reg_code] = {
            "reg_code": reg_code,
            "name": row.get("nimi", "").strip(),
            "legal_form": row.get("ettevotja_oiguslik_vorm", "").strip(),
            "legal_form_subtype": row.get("ettevotja_oigusliku_vormi_alaliik", "").strip(),
            "status": row.get("ettevotja_staatus", "").strip(),
            "status_text": row.get("ettevotja_staatus_tekstina", "").strip(),
            "first_entry_date": row.get("ettevotja_esmakande_kpv", "").strip(),
            "address": row.get("ads_normaliseeritud_taisaadress", "").strip() or row.get("asukoht_ettevotja_aadressis", "").strip(),
            "county": row.get("asukoha_ehak_tekstina", "").strip(),
            "postal_code": row.get("indeks_ettevotja_aadressis", "").strip(),
            "vat_number": row.get("kmkr_nr", "").strip(),
            "registry_link": row.get("teabesysteemi_link", "").strip(),
            # Initialize fields to be filled from other datasets
            "ceo": None,
            "board_members": [],
            "employees": None,
            "revenue": None,
            "profit": None,
            "report_year": None,
        }
    
    return companies


def fetch_persons_data(limit: Optional[int] = None) -> dict[str, list[dict]]:
    """
    Fetch persons associated with companies (board members, CEO, etc.)
    The JSON has nested structure: each entry has kaardile_kantud_isikud list.
    Returns dict keyed by registry code with list of persons.
    """
    zip_content = download_zip(DATASETS["persons_json"])
    data = extract_json_from_zip(zip_content)
    
    print(f"    Loaded {len(data)} company records with persons")
    
    persons_by_company = {}
    for i, record in enumerate(data):
        if limit and i >= limit:
            break
        
        reg_code = str(record.get("ariregistri_kood", "")).strip()
        if not reg_code:
            continue
        
        # Extract persons from nested list
        persons_list = record.get("kaardile_kantud_isikud", [])
        persons = []
        
        for p in persons_list:
            first_name = p.get("eesnimi", "") or ""
            last_name = p.get("nimi_arinimi", "") or ""
            full_name = f"{first_name} {last_name}".strip()
            
            person = {
                "name": full_name,
                "role": p.get("isiku_roll", ""),
                "role_text": p.get("isiku_roll_tekstina", ""),
                "start_date": p.get("algus_kpv", ""),
                "is_legal_person": p.get("isiku_tyyp", "") == "J",
            }
            persons.append(person)
        
        if persons:
            persons_by_company[reg_code] = persons
    
    return persons_by_company


def fetch_reports_mapping() -> dict[str, str]:
    """
    Fetch mapping from report_id to registrikood.
    Returns dict: report_id -> registrikood
    """
    zip_content = download_zip(DATASETS["reports_general"])
    data = extract_csv_from_zip(zip_content)
    
    print(f"    Loaded {len(data)} report records")
    
    # Build mapping: report_id -> (registrikood, year)
    # Keep most recent report per company
    company_best_report = {}  # registrikood -> (report_id, year)
    report_to_company = {}    # report_id -> registrikood
    
    for row in data:
        report_id = row.get("report_id", "").strip()
        reg_code = row.get("registrikood", "").strip()
        year = row.get("aruandeaast", "").strip()
        
        if not report_id or not reg_code:
            continue
        
        report_to_company[report_id] = reg_code
        
        # Track best (most recent) report per company
        if reg_code not in company_best_report:
            company_best_report[reg_code] = (report_id, year)
        elif year > company_best_report[reg_code][1]:
            company_best_report[reg_code] = (report_id, year)
    
    return report_to_company, company_best_report


def fetch_financial_data(report_to_company: dict, limit: Optional[int] = None) -> dict[str, dict]:
    """
    Fetch financial data from annual report elements.
    Returns dict keyed by registry code with financial info.
    """
    # Try 2024 first, then 2023 as fallback
    for year_dataset in ["reports_elements_2024", "reports_elements_2023"]:
        try:
            zip_content = download_zip(DATASETS[year_dataset])
            data = extract_csv_from_zip(zip_content)
            print(f"    Loaded {len(data)} element records")
            break
        except Exception as e:
            print(f"    Could not load {year_dataset}: {e}")
            data = []
    
    if not data:
        return {}
    
    # Aggregate financial data by company
    financials_by_company = defaultdict(dict)
    
    for i, row in enumerate(data):
        if limit and i >= limit:
            break
        
        report_id = row.get("report_id", "").strip()
        reg_code = report_to_company.get(report_id)
        
        if not reg_code:
            continue
        
        label = row.get("elemendi_label", "")
        value = row.get("vaartus", "").strip()
        
        # Map element labels to our fields
        if "Töötajate keskmine arv" in label and "Konsolideeritud" not in label:
            try:
                financials_by_company[reg_code]["employees"] = float(value)
            except (ValueError, TypeError):
                pass
        elif label == "Müügitulu" or (label == "Müügitulu Konsolideeritud" and "revenue" not in financials_by_company[reg_code]):
            financials_by_company[reg_code]["revenue"] = value
        elif label == "Aruandeaasta kasum (kahjum)":
            financials_by_company[reg_code]["profit"] = value
    
    return dict(financials_by_company)


def identify_ceo(persons: list[dict]) -> Optional[str]:
    """
    Identify the CEO from a list of persons.
    """
    # Priority order for CEO-like roles
    ceo_roles = ["JUHL", "JUHATUSE LIIGE", "JUHATUSE ESIMEES", "JUHATAJA", "DIREKTOR", "PROKURIST"]
    
    for role_code in ceo_roles:
        for person in persons:
            role = f"{person.get('role', '')} {person.get('role_text', '')}".upper()
            if role_code in role and person.get("name"):
                return person.get("name")
    
    # Fallback: return first person with a name
    for person in persons:
        if person.get("name"):
            return person.get("name")
    
    return None


def merge_all_data(
    companies: dict[str, dict],
    persons: dict[str, list[dict]],
    financials: dict[str, dict],
    company_best_report: dict[str, tuple]
) -> dict[str, dict]:
    """Merge all datasets into unified company records."""
    
    for reg_code, company in companies.items():
        # Add persons/CEO
        company_persons = persons.get(reg_code, [])
        company["board_members"] = [p.get("name") for p in company_persons if p.get("name")]
        company["ceo"] = identify_ceo(company_persons)
        
        # Add financial data
        fin = financials.get(reg_code, {})
        if fin:
            company["employees"] = fin.get("employees")
            company["revenue"] = fin.get("revenue")
            company["profit"] = fin.get("profit")
        
        # Add report year
        if reg_code in company_best_report:
            company["report_year"] = company_best_report[reg_code][1]
    
    return companies


def print_companies(companies: dict[str, dict], max_print: int = 100):
    """Print company data in a readable format."""
    
    print("\n" + "=" * 80)
    print(f"ESTONIAN BUSINESS REGISTRY DATA - {len(companies)} companies loaded")
    print("=" * 80 + "\n")
    
    for i, (reg_code, c) in enumerate(companies.items()):
        if i >= max_print:
            print(f"\n... and {len(companies) - max_print} more companies")
            break
        
        print(f"[{i+1}] {c['name']}")
        print(f"    Registry Code: {c['reg_code']}")
        print(f"    Legal Form:    {c.get('legal_form', 'N/A')}")
        print(f"    Status:        {c.get('status_text') or c.get('status', 'N/A')}")
        print(f"    Registered:    {c.get('first_entry_date', 'N/A')}")
        print(f"    Address:       {c.get('address', 'N/A')}")
        if c.get('county'):
            print(f"    County:        {c['county']}")
        print(f"    VAT Number:    {c.get('vat_number') or 'N/A'}")
        print(f"    CEO:           {c.get('ceo') or 'N/A'}")
        
        if c.get('board_members'):
            members = c['board_members'][:5]
            extra = f" (+{len(c['board_members'])-5} more)" if len(c['board_members']) > 5 else ""
            print(f"    Board:         {', '.join(members)}{extra}")
        
        emp = c.get('employees')
        year = c.get('report_year', '')
        if emp is not None:
            print(f"    Employees:     {int(emp) if emp == int(emp) else emp}" + (f" ({year})" if year else ""))
        else:
            print(f"    Employees:     N/A")
        
        if c.get('revenue'):
            try:
                rev = float(c['revenue'])
                print(f"    Revenue:       €{rev:,.2f}")
            except:
                print(f"    Revenue:       {c['revenue']}")
        
        if c.get('profit'):
            try:
                prof = float(c['profit'])
                print(f"    Profit:        €{prof:,.2f}")
            except:
                print(f"    Profit:        {c['profit']}")
        
        if c.get('registry_link'):
            print(f"    Link:          {c['registry_link']}")
        
        print()


def main():
    """Main function to fetch and display Estonian business data."""
    
    print("=" * 80)
    print("Estonian Business Registry (e-Äriregister) Open Data Scraper")
    print("Source: https://avaandmed.ariregister.rik.ee")
    print("=" * 80)
    print()
    
    # Set limit to None to fetch ALL data (300k+ companies)
    LIMIT = None
    
    print("Step 1: Fetching basic company data (lihtandmed)...")
    companies = fetch_basic_data(limit=LIMIT)
    print(f"  → Found {len(companies)} companies\n")
    
    print("Step 2: Fetching persons/management data...")
    persons = fetch_persons_data(limit=LIMIT)
    print(f"  → Found persons for {len(persons)} companies\n")
    
    print("Step 3: Fetching annual reports mapping...")
    report_to_company, company_best_report = fetch_reports_mapping()
    print(f"  → Mapped {len(report_to_company)} reports to {len(company_best_report)} companies\n")
    
    print("Step 4: Fetching financial data (employees, revenue, profit)...")
    financials = fetch_financial_data(report_to_company, limit=LIMIT)
    print(f"  → Found financial data for {len(financials)} companies\n")
    
    print("Step 5: Merging all data...")
    companies = merge_all_data(companies, persons, financials, company_best_report)
    print(f"  → Merged data for {len(companies)} companies\n")
    
    # Print results
    print_companies(companies, max_print=100)
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total companies:           {len(companies)}")
    print(f"With CEO identified:       {sum(1 for c in companies.values() if c.get('ceo'))}")
    print(f"With board members:        {sum(1 for c in companies.values() if c.get('board_members'))}")
    print(f"With employee data:        {sum(1 for c in companies.values() if c.get('employees') is not None)}")
    print(f"With revenue data:         {sum(1 for c in companies.values() if c.get('revenue'))}")
    print(f"With profit data:          {sum(1 for c in companies.values() if c.get('profit'))}")
    print(f"With VAT number:           {sum(1 for c in companies.values() if c.get('vat_number'))}")
    print("=" * 80)


if __name__ == "__main__":
    main()
