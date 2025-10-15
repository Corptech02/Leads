#!/usr/bin/env python3
"""
Import Updated Carrier CSV into Vanguard System
This script imports the matched_carriers_20251009_183433_updated.csv file
into the Vanguard system's fmcsa_enhanced table with proper organization.
"""

import sqlite3
import csv
import re
import sys
from datetime import datetime, timedelta
import json

def clean_mc_number(mc_str):
    """Extract MC number from string, removing MC prefix and leading zeros"""
    if not mc_str:
        return None

    # Remove MC prefix and any non-digits
    mc_clean = re.sub(r'^MC-?0*', '', str(mc_str).upper())
    mc_clean = re.sub(r'[^0-9]', '', mc_clean)

    if mc_clean and mc_clean.isdigit():
        return mc_clean
    return None

def clean_dot_number(dot_str):
    """Extract DOT number from string, removing leading zeros"""
    if not dot_str:
        return None

    # Remove any non-digits and leading zeros
    dot_clean = re.sub(r'^0*', '', str(dot_str))
    dot_clean = re.sub(r'[^0-9]', '', dot_clean)

    if dot_clean and dot_clean.isdigit():
        return dot_clean
    return None

def parse_date(date_str):
    """Parse date string and convert to YYYY-MM-DD format"""
    if not date_str or date_str.strip() == '':
        return None

    try:
        # Try MM/DD/YYYY format first
        if '/' in date_str:
            month, day, year = date_str.strip().split('/')
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        # Try YYYY-MM-DD format
        if '-' in date_str and len(date_str.split('-')[0]) == 4:
            return date_str.strip()

    except (ValueError, IndexError):
        pass

    return None

def create_enhanced_carriers_table(conn):
    """Create or update the fmcsa_enhanced table with insurance fields"""
    cursor = conn.cursor()

    # Add new columns for insurance data if they don't exist
    try:
        cursor.execute("ALTER TABLE fmcsa_enhanced ADD COLUMN insurance_company_name TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE fmcsa_enhanced ADD COLUMN insurance_expiration_date DATE")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE fmcsa_enhanced ADD COLUMN insurance_record_raw TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    try:
        cursor.execute("ALTER TABLE fmcsa_enhanced ADD COLUMN days_until_expiry INTEGER")
    except sqlite3.OperationalError:
        pass  # Column already exists

    conn.commit()

def calculate_days_until_expiry(expiry_date):
    """Calculate days until insurance expiry"""
    if not expiry_date:
        return None

    try:
        expiry = datetime.strptime(expiry_date, '%Y-%m-%d')
        today = datetime.now()
        delta = expiry - today
        return delta.days
    except (ValueError, TypeError):
        return None

def import_carrier_data():
    """Import carrier data from updated CSV into Vanguard database"""

    print("Starting enhanced carrier data import...")
    print(f"Time: {datetime.now()}")

    # Connect to Vanguard system database
    vanguard_db_path = '/home/corp06/vanguard-vps-package/vanguard_system.db'
    conn = sqlite3.connect(vanguard_db_path)
    conn.row_factory = sqlite3.Row

    # Create/update table structure
    create_enhanced_carriers_table(conn)

    csv_file_path = '/home/corp06/Leads/matched_carriers_20251009_183433_updated.csv'

    print(f"Reading carrier data from: {csv_file_path}")

    imported_count = 0
    updated_count = 0
    error_count = 0

    with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)

        for row_num, row in enumerate(reader, 1):
            if row_num % 1000 == 0:
                print(f"Processing row {row_num}...")

            try:
                # Clean and extract data
                dot_number = clean_dot_number(row.get('dot_number', ''))
                mc_number = clean_mc_number(row.get('mc_number', ''))
                fmcsa_dot_number = clean_dot_number(row.get('fmcsa_dot_number', ''))

                # Use fmcsa_dot_number as primary, fallback to dot_number
                primary_dot = fmcsa_dot_number if fmcsa_dot_number else dot_number

                if not primary_dot:
                    continue  # Skip records without DOT number

                # Parse insurance data
                insurance_company = row.get('insurance_company', '').strip()
                insurance_expiration = parse_date(row.get('insurance_expiration', ''))
                days_until_expiry = calculate_days_until_expiry(insurance_expiration)

                # Check if record exists
                cursor = conn.cursor()
                cursor.execute("SELECT dot_number FROM fmcsa_enhanced WHERE dot_number = ?", (primary_dot,))
                existing = cursor.fetchone()

                if existing:
                    # Update existing record with insurance data
                    cursor.execute("""
                        UPDATE fmcsa_enhanced SET
                            mc_number = COALESCE(?, mc_number),
                            insurance_carrier = COALESCE(?, insurance_carrier),
                            insurance_company_name = ?,
                            insurance_expiration_date = ?,
                            insurance_record_raw = ?,
                            days_until_expiry = ?,
                            last_updated = CURRENT_TIMESTAMP,
                            data_source = 'matched_carriers_20251009_updated'
                        WHERE dot_number = ?
                    """, (
                        mc_number,
                        insurance_company,
                        insurance_company,
                        insurance_expiration,
                        row.get('insurance_record', ''),
                        days_until_expiry,
                        primary_dot
                    ))
                    updated_count += 1
                else:
                    # Insert new record
                    cursor.execute("""
                        INSERT INTO fmcsa_enhanced (
                            dot_number, mc_number, legal_name, dba_name,
                            street, city, state, zip_code, phone, email_address,
                            power_units, drivers, entity_type, operating_status,
                            insurance_carrier, insurance_company_name,
                            insurance_expiration_date, insurance_record_raw,
                            days_until_expiry, last_updated, data_source, verified
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'matched_carriers_20251009_updated', 1)
                    """, (
                        primary_dot,
                        mc_number,
                        row.get('legal_name', '').strip(),
                        row.get('dba_name', '').strip(),
                        row.get('street', '').strip(),
                        row.get('city', '').strip(),
                        row.get('state', '').strip().upper(),
                        row.get('zip_code', '').strip(),
                        row.get('phone', '').strip(),
                        row.get('email_address', '').strip(),
                        int(row.get('power_units', 0)) if row.get('power_units', '').isdigit() else 0,
                        int(row.get('drivers', 0)) if row.get('drivers', '').isdigit() else 0,
                        row.get('entity_type', '').strip(),
                        row.get('operating_status', '').strip(),
                        insurance_company,  # insurance_carrier (legacy field)
                        insurance_company,  # insurance_company_name (new field)
                        insurance_expiration,
                        row.get('insurance_record', ''),
                        days_until_expiry
                    ))
                    imported_count += 1

                # Commit every 1000 records
                if row_num % 1000 == 0:
                    conn.commit()

            except Exception as e:
                error_count += 1
                print(f"Error processing row {row_num}: {e}")
                continue

    # Final commit
    conn.commit()

    # Create indexes for better performance
    cursor = conn.cursor()
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_fmcsa_insurance_company ON fmcsa_enhanced(insurance_company_name)",
        "CREATE INDEX IF NOT EXISTS idx_fmcsa_expiration_date ON fmcsa_enhanced(insurance_expiration_date)",
        "CREATE INDEX IF NOT EXISTS idx_fmcsa_days_until_expiry ON fmcsa_enhanced(days_until_expiry)",
        "CREATE INDEX IF NOT EXISTS idx_fmcsa_mc_number ON fmcsa_enhanced(mc_number)",
        "CREATE INDEX IF NOT EXISTS idx_fmcsa_state ON fmcsa_enhanced(state)",
        "CREATE INDEX IF NOT EXISTS idx_fmcsa_power_units ON fmcsa_enhanced(power_units)"
    ]

    for index in indexes:
        try:
            cursor.execute(index)
        except sqlite3.OperationalError:
            pass  # Index already exists

    conn.commit()
    conn.close()

    print(f"\n=== Import Summary ===")
    print(f"New records imported: {imported_count:,}")
    print(f"Existing records updated: {updated_count:,}")
    print(f"Total processed: {imported_count + updated_count:,}")
    print(f"Errors encountered: {error_count}")
    print(f"Completed at: {datetime.now()}")

    # Generate summary report
    generate_summary_report(vanguard_db_path)

def generate_summary_report(db_path):
    """Generate a summary report of the imported data"""

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print(f"\n=== Data Summary Report ===")

    # Total records with insurance data
    cursor.execute("SELECT COUNT(*) FROM fmcsa_enhanced WHERE insurance_company_name IS NOT NULL AND insurance_company_name != ''")
    total_with_insurance = cursor.fetchone()[0]
    print(f"Total carriers with insurance data: {total_with_insurance:,}")

    # Insurance companies breakdown
    cursor.execute("""
        SELECT insurance_company_name, COUNT(*) as count
        FROM fmcsa_enhanced
        WHERE insurance_company_name IS NOT NULL AND insurance_company_name != ''
        GROUP BY insurance_company_name
        ORDER BY count DESC
        LIMIT 10
    """)

    print(f"\nTop 10 Insurance Companies:")
    for company, count in cursor.fetchall():
        print(f"  {company}: {count:,} carriers")

    # Expiring insurance breakdown
    cursor.execute("""
        SELECT
            CASE
                WHEN days_until_expiry <= 30 THEN '0-30 days'
                WHEN days_until_expiry <= 60 THEN '31-60 days'
                WHEN days_until_expiry <= 90 THEN '61-90 days'
                WHEN days_until_expiry <= 180 THEN '91-180 days'
                ELSE '180+ days'
            END as expiry_range,
            COUNT(*) as count
        FROM fmcsa_enhanced
        WHERE days_until_expiry IS NOT NULL
        GROUP BY expiry_range
        ORDER BY MIN(COALESCE(days_until_expiry, 999999))
    """)

    print(f"\nInsurance Expiration Breakdown:")
    for range_label, count in cursor.fetchall():
        print(f"  {range_label}: {count:,} carriers")

    # State breakdown
    cursor.execute("""
        SELECT state, COUNT(*) as count
        FROM fmcsa_enhanced
        WHERE state IS NOT NULL AND state != ''
        GROUP BY state
        ORDER BY count DESC
        LIMIT 10
    """)

    print(f"\nTop 10 States by Carrier Count:")
    for state, count in cursor.fetchall():
        print(f"  {state}: {count:,} carriers")

    conn.close()

if __name__ == "__main__":
    import_carrier_data()