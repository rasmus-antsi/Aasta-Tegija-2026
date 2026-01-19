"""
Management command to import Estonian business data from open data portal.
Usage: python manage.py import_companies [--limit N]
"""

import requests
import zipfile
import io
import csv
import json
from decimal import Decimal, InvalidOperation
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from a_main.models import Company


BASE_URL = "https://avaandmed.ariregister.rik.ee"

DATASETS = {
    "basic_csv": f"{BASE_URL}/sites/default/files/avaandmed/ettevotja_rekvisiidid__lihtandmed.csv.zip",
    "general_json": f"{BASE_URL}/sites/default/files/avaandmed/ettevotja_rekvisiidid__yldandmed.json.zip",
    "persons_json": f"{BASE_URL}/sites/default/files/avaandmed/ettevotja_rekvisiidid__kaardile_kantud_isikud.json.zip",
    "reports_general": f"{BASE_URL}/sites/default/files/1.aruannete_yldandmed_kuni_31122025_0.zip",
    "reports_elements_2024": f"{BASE_URL}/sites/default/files/4.2024_aruannete_elemendid_kuni_31122025_0.zip",
}


class Command(BaseCommand):
    help = 'Import Estonian business data from ariregister.rik.ee open data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of companies to import (for testing)',
        )
        parser.add_argument(
            '--filter-complete',
            action='store_true',
            help='Only import companies with all required fields',
        )

    def handle(self, *args, **options):
        limit = options['limit']
        filter_complete = options['filter_complete']
        
        self.stdout.write("=" * 60)
        self.stdout.write("Estonian Business Registry Data Import")
        self.stdout.write("=" * 60)
        
        # Step 1: Fetch basic data
        self.stdout.write("\nStep 1: Fetching basic company data...")
        companies = self.fetch_basic_data(limit)
        self.stdout.write(f"  → Found {len(companies)} companies")
        
        # Step 2: Fetch general data (for EMTAK activity codes)
        self.stdout.write("\nStep 2: Fetching activity codes (EMTAK)...")
        activities = self.fetch_activity_data(limit)
        self.stdout.write(f"  → Found activities for {len(activities)} companies")
        
        # Step 3: Fetch persons data
        self.stdout.write("\nStep 3: Fetching persons/management data...")
        persons = self.fetch_persons_data(limit)
        self.stdout.write(f"  → Found persons for {len(persons)} companies")
        
        # Step 4: Fetch financial data
        self.stdout.write("\nStep 4: Fetching report mapping...")
        report_to_company = self.fetch_reports_mapping()
        self.stdout.write(f"  → Mapped {len(report_to_company)} reports")
        
        self.stdout.write("\nStep 5: Fetching financial data...")
        financials = self.fetch_financial_data(report_to_company, limit)
        self.stdout.write(f"  → Found financials for {len(financials)} companies")
        
        # Step 6: Merge and save
        self.stdout.write("\nStep 6: Merging and saving to database...")
        saved, skipped = self.save_companies(
            companies, activities, persons, financials, filter_complete
        )
        
        self.stdout.write(self.style.SUCCESS(f"\n✓ Saved {saved} companies to database"))
        if skipped:
            self.stdout.write(f"  Skipped {skipped} companies (incomplete data)")
        
        # Summary
        total = Company.objects.count()
        complete = Company.get_complete_companies().count()
        self.stdout.write(f"\nDatabase now contains {total} companies ({complete} with complete data)")

    def download_zip(self, url):
        """Download a zip file."""
        filename = url.split('/')[-1]
        self.stdout.write(f"    Downloading: {filename}")
        response = requests.get(url, timeout=600)
        response.raise_for_status()
        return response.content

    def extract_csv(self, zip_content, delimiter=';'):
        """Extract and parse CSV from zip."""
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
            if not csv_files:
                return []
            with zf.open(csv_files[0]) as f:
                content = f.read().decode('utf-8-sig')
                return list(csv.DictReader(io.StringIO(content), delimiter=delimiter))

    def extract_json(self, zip_content):
        """Extract and parse JSON from zip."""
        with zipfile.ZipFile(io.BytesIO(zip_content)) as zf:
            json_files = [f for f in zf.namelist() if f.endswith('.json')]
            if not json_files:
                return []
            with zf.open(json_files[0]) as f:
                content = f.read().decode('utf-8-sig')
                return json.loads(content)

    def fetch_basic_data(self, limit=None):
        """Fetch basic company data."""
        zip_content = self.download_zip(DATASETS["basic_csv"])
        data = self.extract_csv(zip_content)
        
        companies = {}
        for i, row in enumerate(data):
            if limit and i >= limit:
                break
            
            reg_code = row.get("ariregistri_kood", "").strip()
            if not reg_code:
                continue
            
            companies[reg_code] = {
                "name": row.get("nimi", "").strip(),
                "registry_code": reg_code,
                "legal_form": row.get("ettevotja_oiguslik_vorm", "").strip(),
                "status": row.get("ettevotja_staatus", "").strip(),
                "status_text": row.get("ettevotja_staatus_tekstina", "").strip(),
                "registered_date": row.get("ettevotja_esmakande_kpv", "").strip(),
                "address": row.get("ads_normaliseeritud_taisaadress", "").strip(),
                "county": row.get("asukoha_ehak_tekstina", "").strip(),
                "postal_code": row.get("indeks_ettevotja_aadressis", "").strip(),
                "vat_number": row.get("kmkr_nr", "").strip(),
                "registry_link": row.get("teabesysteemi_link", "").strip(),
            }
        
        return companies

    def fetch_activity_data(self, limit=None):
        """Fetch EMTAK activity codes from general data."""
        zip_content = self.download_zip(DATASETS["general_json"])
        data = self.extract_json(zip_content)
        
        activities = {}
        for i, record in enumerate(data):
            if limit and i >= limit:
                break
            
            reg_code = str(record.get("ariregistri_kood", "")).strip()
            if not reg_code:
                continue
            
            yldandmed = record.get("yldandmed", {})
            tegevusalad = yldandmed.get("teatatud_tegevusalad", [])
            
            if tegevusalad:
                # Get primary activity (marked as põhitegevusala) or first one
                primary = None
                for t in tegevusalad:
                    if not primary:
                        primary = t
                    # Some entries might have a primary flag
                
                if primary:
                    activities[reg_code] = {
                        "activity_code": primary.get("emtak_kood", ""),
                        "activity": primary.get("emtak_tekstina", ""),
                    }
        
        return activities

    def fetch_persons_data(self, limit=None):
        """Fetch persons associated with companies."""
        zip_content = self.download_zip(DATASETS["persons_json"])
        data = self.extract_json(zip_content)
        
        persons_by_company = {}
        for i, record in enumerate(data):
            if limit and i >= limit:
                break
            
            reg_code = str(record.get("ariregistri_kood", "")).strip()
            if not reg_code:
                continue
            
            persons_list = record.get("kaardile_kantud_isikud", [])
            persons = []
            
            for p in persons_list:
                first_name = p.get("eesnimi", "") or ""
                last_name = p.get("nimi_arinimi", "") or ""
                full_name = f"{first_name} {last_name}".strip()
                
                if full_name:
                    persons.append({
                        "name": full_name,
                        "role": p.get("isiku_roll", ""),
                        "role_text": p.get("isiku_roll_tekstina", ""),
                    })
            
            if persons:
                persons_by_company[reg_code] = persons
        
        return persons_by_company

    def fetch_reports_mapping(self):
        """Fetch mapping from report_id to registrikood."""
        zip_content = self.download_zip(DATASETS["reports_general"])
        data = self.extract_csv(zip_content)
        
        report_to_company = {}
        for row in data:
            report_id = row.get("report_id", "").strip()
            reg_code = row.get("registrikood", "").strip()
            if report_id and reg_code:
                report_to_company[report_id] = reg_code
        
        return report_to_company

    def fetch_financial_data(self, report_to_company, limit=None):
        """Fetch financial data from annual reports."""
        zip_content = self.download_zip(DATASETS["reports_elements_2024"])
        data = self.extract_csv(zip_content)
        
        financials = defaultdict(dict)
        
        for i, row in enumerate(data):
            if limit and i >= limit * 10:  # More elements per company
                break
            
            report_id = row.get("report_id", "").strip()
            reg_code = report_to_company.get(report_id)
            if not reg_code:
                continue
            
            label = row.get("elemendi_label", "")
            value = row.get("vaartus", "").strip()
            
            if "Töötajate keskmine arv" in label and "Konsolideeritud" not in label:
                try:
                    financials[reg_code]["employees"] = float(value)
                except (ValueError, TypeError):
                    pass
            elif label == "Müügitulu":
                financials[reg_code]["revenue"] = value
            elif label == "Aruandeaasta kasum (kahjum)":
                financials[reg_code]["profit"] = value
            elif label == "Tööjõukulud":
                financials[reg_code]["labor_taxes"] = value
        
        return dict(financials)

    def identify_ceo(self, persons):
        """Identify CEO from persons list."""
        ceo_roles = ["JUHL", "JUHATUSE LIIGE", "JUHATUSE ESIMEES"]
        
        for role_code in ceo_roles:
            for person in persons:
                role = f"{person.get('role', '')} {person.get('role_text', '')}".upper()
                if role_code in role and person.get("name"):
                    return person.get("name")
        
        if persons:
            return persons[0].get("name", "")
        return ""

    def to_decimal(self, value):
        """Convert value to Decimal or None."""
        if not value:
            return None
        try:
            return Decimal(str(value).replace(",", "."))
        except (InvalidOperation, ValueError):
            return None

    @transaction.atomic
    def save_companies(self, companies, activities, persons, financials, filter_complete):
        """Save all companies to database."""
        saved = 0
        skipped = 0
        batch = []
        batch_size = 1000
        
        for reg_code, company in companies.items():
            # Merge data
            activity = activities.get(reg_code, {})
            company_persons = persons.get(reg_code, [])
            fin = financials.get(reg_code, {})
            
            # Build company object
            obj = Company(
                name=company.get("name", ""),
                registry_code=reg_code,
                legal_form=company.get("legal_form", ""),
                status=company.get("status", ""),
                status_text=company.get("status_text", ""),
                registered_date=company.get("registered_date", ""),
                address=company.get("address", ""),
                county=company.get("county", ""),
                postal_code=company.get("postal_code", ""),
                activity_code=activity.get("activity_code", ""),
                activity=activity.get("activity", ""),
                vat_number=company.get("vat_number", ""),
                ceo=self.identify_ceo(company_persons),
                board_members=", ".join(p.get("name", "") for p in company_persons),
                employees=fin.get("employees"),
                revenue=self.to_decimal(fin.get("revenue")),
                profit=self.to_decimal(fin.get("profit")),
                labor_taxes=self.to_decimal(fin.get("labor_taxes")),
                registry_link=company.get("registry_link", ""),
            )
            
            # Filter if requested
            if filter_complete:
                if not all([
                    obj.name, obj.registry_code, obj.county, obj.activity,
                    obj.employees is not None, obj.revenue is not None
                ]):
                    skipped += 1
                    continue
            
            batch.append(obj)
            
            if len(batch) >= batch_size:
                Company.objects.bulk_create(
                    batch,
                    update_conflicts=True,
                    unique_fields=['registry_code'],
                    update_fields=[
                        'name', 'legal_form', 'status', 'status_text', 'registered_date',
                        'address', 'county', 'postal_code', 'activity_code', 'activity',
                        'vat_number', 'ceo', 'board_members', 'employees', 'revenue',
                        'profit', 'labor_taxes', 'registry_link'
                    ]
                )
                saved += len(batch)
                self.stdout.write(f"    Saved {saved} companies...")
                batch = []
        
        # Save remaining
        if batch:
            Company.objects.bulk_create(
                batch,
                update_conflicts=True,
                unique_fields=['registry_code'],
                update_fields=[
                    'name', 'legal_form', 'status', 'status_text', 'registered_date',
                    'address', 'county', 'postal_code', 'activity_code', 'activity',
                    'vat_number', 'ceo', 'board_members', 'employees', 'revenue',
                    'profit', 'labor_taxes', 'registry_link'
                ]
            )
            saved += len(batch)
        
        return saved, skipped
