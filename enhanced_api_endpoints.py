#!/usr/bin/env python3
"""
Enhanced API Endpoints for Vanguard System
New endpoints that utilize the updated carrier data with insurance company and expiration information
"""

from fastapi import FastAPI, HTTPException, Request, Query
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
import sqlite3
from contextlib import contextmanager

# Database connection manager
@contextmanager
def get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

# Enhanced search endpoint with insurance filtering
async def enhanced_search_carriers(request: Request):
    """Enhanced search with insurance company and expiration date filtering"""
    try:
        data = await request.json()

        with get_db("vanguard_system.db") as conn:
            cursor = conn.cursor()

            # Base query using the enhanced table
            query = """
                SELECT dot_number, mc_number, legal_name, dba_name,
                       street, city, state, zip_code, phone, email_address,
                       power_units, drivers, insurance_carrier,
                       insurance_company_name, insurance_expiration_date,
                       days_until_expiry, operating_status, entity_type
                FROM fmcsa_enhanced WHERE 1=1
            """
            params = []

            # Basic filters
            if data.get("usdot_number"):
                query += " AND dot_number LIKE ?"
                params.append(f"%{data['usdot_number']}%")

            if data.get("mc_number"):
                query += " AND mc_number LIKE ?"
                params.append(f"%{data['mc_number']}%")

            if data.get("legal_name"):
                query += " AND (legal_name LIKE ? OR dba_name LIKE ?)"
                params.extend([f"%{data['legal_name']}%", f"%{data['legal_name']}%"])

            if data.get("state"):
                query += " AND state = ?"
                params.append(data["state"].upper())

            # Enhanced insurance filters
            if data.get("insurance_company"):
                query += " AND insurance_company_name LIKE ?"
                params.append(f"%{data['insurance_company']}%")

            if data.get("expiring_within_days"):
                days = int(data["expiring_within_days"])
                query += " AND days_until_expiry <= ? AND days_until_expiry > 0"
                params.append(days)

            if data.get("min_expiry_days"):
                query += " AND days_until_expiry >= ?"
                params.append(int(data["min_expiry_days"]))

            if data.get("max_expiry_days"):
                query += " AND days_until_expiry <= ?"
                params.append(int(data["max_expiry_days"]))

            if data.get("expiry_date_from"):
                query += " AND insurance_expiration_date >= ?"
                params.append(data["expiry_date_from"])

            if data.get("expiry_date_to"):
                query += " AND insurance_expiration_date <= ?"
                params.append(data["expiry_date_to"])

            if data.get("has_insurance_only"):
                query += " AND insurance_company_name IS NOT NULL AND insurance_company_name != ''"

            if data.get("min_power_units"):
                query += " AND power_units >= ?"
                params.append(int(data["min_power_units"]))

            if data.get("operating_status"):
                query += " AND operating_status = ?"
                params.append(data["operating_status"])

            # Pagination
            page = data.get("page", 1)
            per_page = min(data.get("per_page", 100), 500)
            offset = (page - 1) * per_page

            # Get total count
            count_query = query.replace("SELECT dot_number, mc_number, legal_name, dba_name, street, city, state, zip_code, phone, email_address, power_units, drivers, insurance_carrier, insurance_company_name, insurance_expiration_date, days_until_expiry, operating_status, entity_type", "SELECT COUNT(*)")
            cursor.execute(count_query, params)
            total = cursor.fetchone()[0]

            # Get results with ordering
            order_by = data.get("order_by", "days_until_expiry")
            order_dir = data.get("order_direction", "ASC")

            if order_by in ["days_until_expiry", "insurance_expiration_date", "power_units", "legal_name"]:
                query += f" ORDER BY {order_by} {order_dir}"

            query += f" LIMIT {per_page} OFFSET {offset}"
            cursor.execute(query, params)

            results = []
            for row in cursor.fetchall():
                carrier = dict(row)

                # Calculate priority based on expiry
                priority = "low"
                if carrier.get("days_until_expiry"):
                    days = carrier["days_until_expiry"]
                    if days <= 30:
                        priority = "high"
                    elif days <= 60:
                        priority = "medium"

                # Format for frontend compatibility
                results.append({
                    "usdot_number": carrier.get("dot_number", ""),
                    "legal_name": carrier.get("legal_name", ""),
                    "dba_name": carrier.get("dba_name", ""),
                    "city": carrier.get("city", ""),
                    "state": carrier.get("state", ""),
                    "power_units": carrier.get("power_units", 0),
                    "mc_number": carrier.get("mc_number", ""),
                    "phone": carrier.get("phone", ""),
                    "email_address": carrier.get("email_address", ""),
                    "status": carrier.get("operating_status", "Unknown"),
                    "insurance_company": carrier.get("insurance_company_name", ""),
                    "insurance_expiry": carrier.get("insurance_expiration_date", ""),
                    "days_until_expiry": carrier.get("days_until_expiry", None),
                    "priority": priority,
                    "address": f"{carrier.get('street', '')} {carrier.get('city', '')} {carrier.get('state', '')} {carrier.get('zip_code', '')}".strip()
                })

            return {
                "results": results,
                "total": total,
                "page": page,
                "per_page": per_page,
                "carriers": results,  # For frontend compatibility
                "criteria_applied": {
                    "insurance_filters": bool(data.get("insurance_company") or data.get("expiring_within_days")),
                    "expiry_filters": bool(data.get("expiry_date_from") or data.get("expiry_date_to")),
                    "total_filters": len([k for k, v in data.items() if v])
                }
            }

    except Exception as e:
        print(f"Enhanced search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def get_insurance_leads_advanced(
    expiring_within_days: int = Query(30, description="Days until insurance expiry"),
    limit: int = Query(2000, description="Maximum number of leads"),
    state: Optional[str] = Query(None, description="State filter"),
    insurance_companies: Optional[str] = Query(None, description="Comma-separated insurance companies"),
    min_power_units: Optional[int] = Query(1, description="Minimum power units"),
    exclude_companies: Optional[str] = Query(None, description="Insurance companies to exclude"),
    priority_only: bool = Query(False, description="Only high priority leads (30 days or less)")
):
    """Advanced insurance leads with comprehensive filtering"""

    print(f"Getting advanced insurance leads: days={expiring_within_days}, state={state}")

    with get_db("vanguard_system.db") as conn:
        cursor = conn.cursor()

        query = """
            SELECT dot_number, mc_number, legal_name, dba_name,
                   street, city, state, zip_code, phone, email_address,
                   power_units, drivers, insurance_company_name,
                   insurance_expiration_date, days_until_expiry,
                   operating_status, entity_type
            FROM fmcsa_enhanced
            WHERE insurance_company_name IS NOT NULL
            AND insurance_company_name != ''
            AND days_until_expiry IS NOT NULL
            AND days_until_expiry > 0
            AND days_until_expiry <= ?
        """
        params = [expiring_within_days]

        # Add filters
        if state:
            query += " AND state = ?"
            params.append(state.upper())

        if min_power_units:
            query += " AND power_units >= ?"
            params.append(min_power_units)

        if insurance_companies:
            companies = [c.strip() for c in insurance_companies.split(',')]
            placeholders = ','.join(['?' for _ in companies])
            query += f" AND insurance_company_name IN ({placeholders})"
            params.extend(companies)

        if exclude_companies:
            excluded = [c.strip() for c in exclude_companies.split(',')]
            placeholders = ','.join(['?' for _ in excluded])
            query += f" AND insurance_company_name NOT IN ({placeholders})"
            params.extend(excluded)

        if priority_only:
            query += " AND days_until_expiry <= 30"

        # Order by priority (soonest expiry first)
        query += " ORDER BY days_until_expiry ASC, power_units DESC"

        # Apply limit
        query += " LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        results = []

        for row in cursor.fetchall():
            carrier = dict(row)

            # Calculate lead score
            lead_score = 100
            days = carrier.get("days_until_expiry", 999)
            power_units = carrier.get("power_units", 0)

            # Adjust score based on urgency
            if days <= 15:
                lead_score += 50
            elif days <= 30:
                lead_score += 30
            elif days <= 60:
                lead_score += 10

            # Adjust score based on fleet size
            if power_units >= 10:
                lead_score += 20
            elif power_units >= 5:
                lead_score += 10

            # Priority classification
            priority = "low"
            if days <= 15:
                priority = "critical"
            elif days <= 30:
                priority = "high"
            elif days <= 60:
                priority = "medium"

            results.append({
                **dict(carrier),
                "lead_score": lead_score,
                "priority": priority,
                "contact_urgency": "immediate" if days <= 15 else "high" if days <= 30 else "normal"
            })

        return {
            "leads": results,
            "total": len(results),
            "criteria": {
                "expiring_within_days": expiring_within_days,
                "state": state,
                "insurance_companies": insurance_companies,
                "min_power_units": min_power_units,
                "priority_only": priority_only
            },
            "summary": {
                "critical_leads": len([l for l in results if l["priority"] == "critical"]),
                "high_priority": len([l for l in results if l["priority"] == "high"]),
                "average_lead_score": sum(l["lead_score"] for l in results) / len(results) if results else 0
            }
        }


async def get_insurance_company_analysis():
    """Get analysis of insurance companies in the database"""

    with get_db("vanguard_system.db") as conn:
        cursor = conn.cursor()

        # Overall statistics
        cursor.execute("""
            SELECT
                COUNT(*) as total_carriers,
                COUNT(CASE WHEN insurance_company_name IS NOT NULL AND insurance_company_name != '' THEN 1 END) as carriers_with_insurance,
                COUNT(CASE WHEN days_until_expiry <= 30 THEN 1 END) as expiring_30_days,
                COUNT(CASE WHEN days_until_expiry <= 60 THEN 1 END) as expiring_60_days,
                COUNT(CASE WHEN days_until_expiry <= 90 THEN 1 END) as expiring_90_days
            FROM fmcsa_enhanced
        """)

        stats = dict(cursor.fetchone())

        # Insurance company breakdown
        cursor.execute("""
            SELECT
                insurance_company_name,
                COUNT(*) as carrier_count,
                COUNT(CASE WHEN days_until_expiry <= 30 THEN 1 END) as expiring_30_days,
                COUNT(CASE WHEN days_until_expiry <= 60 THEN 1 END) as expiring_60_days,
                AVG(power_units) as avg_fleet_size,
                AVG(days_until_expiry) as avg_days_until_expiry
            FROM fmcsa_enhanced
            WHERE insurance_company_name IS NOT NULL AND insurance_company_name != ''
            GROUP BY insurance_company_name
            ORDER BY carrier_count DESC
            LIMIT 50
        """)

        companies = [dict(row) for row in cursor.fetchall()]

        # State breakdown for expiring insurance
        cursor.execute("""
            SELECT
                state,
                COUNT(*) as total_carriers,
                COUNT(CASE WHEN days_until_expiry <= 30 THEN 1 END) as expiring_30_days,
                COUNT(CASE WHEN days_until_expiry <= 60 THEN 1 END) as expiring_60_days
            FROM fmcsa_enhanced
            WHERE insurance_company_name IS NOT NULL AND insurance_company_name != ''
            GROUP BY state
            ORDER BY expiring_30_days DESC
            LIMIT 25
        """)

        states = [dict(row) for row in cursor.fetchall()]

        return {
            "overall_stats": stats,
            "insurance_companies": companies,
            "state_breakdown": states,
            "generated_at": datetime.now().isoformat()
        }


# Additional utility endpoints

async def get_expiry_calendar():
    """Get insurance expiry calendar view"""

    with get_db("vanguard_system.db") as conn:
        cursor = conn.cursor()

        # Get expiries by month for next 12 months
        cursor.execute("""
            SELECT
                strftime('%Y-%m', insurance_expiration_date) as expiry_month,
                COUNT(*) as carrier_count,
                COUNT(CASE WHEN power_units >= 5 THEN 1 END) as large_fleets
            FROM fmcsa_enhanced
            WHERE insurance_expiration_date IS NOT NULL
            AND insurance_expiration_date >= date('now')
            AND insurance_expiration_date <= date('now', '+12 months')
            GROUP BY expiry_month
            ORDER BY expiry_month
        """)

        calendar_data = [dict(row) for row in cursor.fetchall()]

        return {
            "calendar": calendar_data,
            "total_upcoming_expiries": sum(month["carrier_count"] for month in calendar_data)
        }


# Function to add these endpoints to existing FastAPI app
def add_enhanced_endpoints(app):
    """Add enhanced endpoints to the existing FastAPI app"""

    app.add_api_route("/api/search/enhanced", enhanced_search_carriers, methods=["POST"])
    app.add_api_route("/api/leads/insurance-advanced", get_insurance_leads_advanced, methods=["GET"])
    app.add_api_route("/api/analytics/insurance-companies", get_insurance_company_analysis, methods=["GET"])
    app.add_api_route("/api/analytics/expiry-calendar", get_expiry_calendar, methods=["GET"])

    return app