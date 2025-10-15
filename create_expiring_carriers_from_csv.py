#!/usr/bin/env python3
"""
Create expiring carriers file from the CSV data
Filters for carriers with insurance expiring in the next 50 days
"""

import csv
import os
from datetime import datetime, timedelta
import pandas as pd

def parse_date(date_str):
    """Parse date string in various formats"""
    if not date_str or date_str.strip() == '':
        return None

    date_str = str(date_str).strip()

    # Try common date formats
    formats = ['%Y-%m-%d', '%m/%d/%Y', '%Y/%m/%d', '%d/%m/%Y']

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None

def days_until_expiry(expiry_date):
    """Calculate days until expiry"""
    if not expiry_date:
        return None

    today = datetime.now()
    delta = expiry_date - today
    return delta.days

def create_expiring_carriers_file():
    # Input and output files
    input_file = "/home/corp06/Leads/matched_carriers_20251009_183433_updated.csv"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"/home/corp06/Leads/expiring_carriers_50_days_{timestamp}.csv"

    print(f"🔍 Processing CSV file: {input_file}")

    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return None

    try:
        # Read CSV with pandas for better performance
        print("📊 Reading CSV file...")
        df = pd.read_csv(input_file, low_memory=False)

        print(f"✅ Loaded {len(df):,} total records")
        print(f"📋 Columns: {list(df.columns)}")

        # Check for insurance columns
        insurance_cols = [col for col in df.columns if 'insurance' in col.lower()]
        print(f"🏥 Insurance columns found: {insurance_cols}")

        if not insurance_cols:
            print("❌ No insurance columns found in CSV")
            return None

        # Filter for records with insurance data
        has_insurance = df[insurance_cols[0]].notna() & (df[insurance_cols[0]] != '')
        insurance_records = df[has_insurance].copy()

        print(f"📄 Records with insurance data: {len(insurance_records):,}")

        if len(insurance_records) == 0:
            print("❌ No records with insurance data found")
            return None

        # Find expiration date column
        expiry_col = None
        for col in df.columns:
            if 'expir' in col.lower() or 'expir' in col.lower():
                expiry_col = col
                break

        if not expiry_col:
            print("❌ No expiration date column found")
            return None

        print(f"📅 Using expiration column: {expiry_col}")

        # Calculate days until expiry for records with valid dates
        print("🧮 Calculating days until expiry...")

        expiring_records = []
        processed = 0

        for _, row in insurance_records.iterrows():
            processed += 1
            if processed % 10000 == 0:
                print(f"   Processed {processed:,} records...")

            expiry_str = str(row[expiry_col]) if pd.notna(row[expiry_col]) else ''

            if not expiry_str or expiry_str.lower() in ['nan', 'none', '']:
                continue

            expiry_date = parse_date(expiry_str)
            if not expiry_date:
                continue

            days_until = days_until_expiry(expiry_date)
            if days_until is None:
                continue

            # Filter for expiring in next 50 days (including 30 days past due for renewals)
            if -30 <= days_until <= 50:
                # Create a record with all original data plus calculated fields
                record = row.to_dict()
                record['days_until_expiry'] = days_until
                record['expiry_urgency'] = 'URGENT' if days_until <= 7 else 'HIGH' if days_until <= 30 else 'MEDIUM'
                expiring_records.append(record)

        print(f"✅ Found {len(expiring_records):,} carriers expiring in next 50 days")

        if len(expiring_records) == 0:
            print("❌ No carriers found expiring in the next 50 days")
            return None

        # Sort by urgency (soonest expiring first)
        expiring_records.sort(key=lambda x: x['days_until_expiry'])

        # Write to CSV
        print(f"💾 Writing to CSV file: {output_file}")

        # Get column names from first record
        if expiring_records:
            fieldnames = list(expiring_records[0].keys())

            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(expiring_records)

        # Get file size
        file_size = os.path.getsize(output_file)
        file_size_mb = file_size / (1024 * 1024)

        print(f"✅ Export completed successfully!")
        print(f"📄 File: {output_file}")
        print(f"📊 Records: {len(expiring_records):,}")
        print(f"💾 Size: {file_size_mb:.2f} MB")

        # Show distribution by urgency
        urgency_counts = {}
        for record in expiring_records:
            urgency = record['expiry_urgency']
            urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1

        print(f"\n🎯 Urgency Distribution:")
        for urgency, count in urgency_counts.items():
            print(f"   {urgency}: {count:,} carriers")

        # Show sample of urgent records
        urgent_records = [r for r in expiring_records if r['expiry_urgency'] == 'URGENT']
        if urgent_records:
            print(f"\n🚨 Sample of URGENT carriers (expiring in ≤7 days):")
            for i, record in enumerate(urgent_records[:3]):
                legal_name = record.get('legal_name', 'N/A')
                state = record.get('state', 'N/A')
                days = record['days_until_expiry']
                insurance = record.get('insurance_company', 'N/A')
                print(f"   {i+1}. {legal_name} ({state}) - {insurance} expires in {days} days")

        return output_file

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    create_expiring_carriers_file()