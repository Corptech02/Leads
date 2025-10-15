# Vanguard Lead Generation System - Complete Documentation

## Overview
This document provides comprehensive documentation for the Vanguard Insurance lead generation system, specifically covering the month-based filtering implementation and troubleshooting guide created on October 11, 2025.

## System Architecture

### Components
1. **Frontend JavaScript Override**: `/var/www/vanguard/js/fcsma-api-override-v5.js`
2. **Python Flask API**: `/var/www/vanguard/api/matched-carriers-leads.py` (Port 5002)
3. **Node.js Proxy Backend**: `/var/www/vanguard/backend/server.js` (Port 3001)
4. **Data Source**: `/home/corp06/matched_carriers_20251009_183433.csv` (383K+ records)

### Data Flow
```
Browser → JavaScript Override → Node.js Backend (3001) → Python API (5002) → CSV Database
```

## Key Features Implemented

### 1. Month-Based Insurance Expiration Filtering
**Problem Solved**: Insurance policies renew annually on the same month/day regardless of year. The system needed to filter leads based on renewal dates within X days from today, ignoring the year component.

**Solution**:
- Extract month/day from insurance expiration dates
- Project these to current/next year based on whether the date has already passed
- Filter only future dates within the specified range (30, 60, 90 days, etc.)

### 2. Multi-Company Selection Fix
**Problem Solved**: Selecting multiple insurance companies returned 0 results due to company name truncation.

**Solution**: Smart company name mapping that preserves multi-word company names like "Progressive Preferred Insurance Company".

### 3. Proper API Response Handling
**Problem Solved**: JavaScript expected `data.success` but API returned `data.status === 'success'`.

**Solution**: Updated condition to handle both response formats.

## Critical Configuration Files

### 1. JavaScript Override (`/var/www/vanguard/js/fcsma-api-override-v5.js`)

**Key Functions**:
- `queryMatchedCarriersDataForced()`: Main API calling function
- Smart company name mapping for multi-word insurance companies
- Response format compatibility handling

**Current Cache Buster**: `v=20251011_0153`

**Important Settings**:
```javascript
limit: Math.min(criteria.limit || 5000, 5000),  // Max 5000 leads
month_based: 'true'  // Enables month-based filtering
```

### 2. Python API (`/var/www/vanguard/api/matched-carriers-leads.py`)

**Key Functions**:
- `extract_expiration_date()`: Parses insurance expiration dates
- Month-based filtering logic in main endpoint
- Date projection to current/next year

**Critical Algorithm**:
```python
if month_based:
    # Project month/day to current year first
    current_year_expiry = today.replace(month=expiry_month_day[0], day=expiry_month_day[1])

    # If already passed this year, project to next year
    if current_year_expiry <= today:
        projected_expiry = current_year_expiry.replace(year=today.year + 1)
    else:
        projected_expiry = current_year_expiry

    # Filter within date range
    if projected_expiry < start_date or projected_expiry > end_date:
        continue
```

### 3. Node.js Backend (`/var/www/vanguard/backend/server.js`)

**Critical Configuration**:
```javascript
// Line 165: Correct proxy port
const response = await axios.get('http://localhost:5002/api/matched-carriers-leads', {
```

### 4. HTML Cache Buster (`/var/www/vanguard/index.html`)

**Current Version**:
```html
<script src="js/fcsma-api-override-v5.js?v=20251011_0153"></script>
```

## Troubleshooting Guide

### Issue 1: Constant 708 Leads Returned
**Symptoms**: Same number of leads regardless of filters
**Root Cause**: Month-based filtering logic was broken
**Solution**: Fixed date projection algorithm in Python API
**Files Modified**: `/var/www/vanguard/api/matched-carriers-leads.py`

### Issue 2: Multi-Company Selection Returns 0 Results
**Symptoms**: Single company works, multiple companies return empty
**Root Cause**: Company name truncation in JavaScript
**Solution**: Smart company name mapping
**Files Modified**: `/var/www/vanguard/js/fcsma-api-override-v5.js`

### Issue 3: API Connection Refused (Port 5003)
**Symptoms**: Browser console shows "connect ECONNREFUSED 127.0.0.1:5003"
**Root Cause**: Node.js backend proxying to wrong port
**Solution**: Changed proxy from port 5003 to 5002
**Files Modified**: `/var/www/vanguard/backend/server.js`

### Issue 4: JavaScript Response Format Error
**Symptoms**: API returns data but JavaScript throws error
**Root Cause**: Mismatch between expected `data.success` and actual `data.status`
**Solution**: Updated condition to handle both formats
**Files Modified**: `/var/www/vanguard/js/fcsma-api-override-v5.js`

## System Status Commands

### Check Running Services
```bash
# Python API (Port 5002)
ss -tlnp | grep :5002

# Node.js Backend (Port 3001)
ss -tlnp | grep :3001

# View API logs
tail -f /var/www/vanguard/logs/matched-carriers-api.log
```

### Restart Services
```bash
# Kill existing processes
killall python3
lsof -ti :5002 | xargs -r kill -9
lsof -ti :3001 | xargs -r kill -9

# Start Python API
cd /var/www/vanguard && python3 api/matched-carriers-leads.py &

# Start Node.js Backend
cd /var/www/vanguard/backend && nohup node server.js > server.log 2>&1 &
```

### Test API Directly
```bash
# Test 30-day Progressive filter
curl -s "http://localhost:5002/api/matched-carriers-leads?state=OH&days=30&insurance_companies=Progressive&limit=10&month_based=true" | python3 -m json.tool

# Test 60-day filter to verify scaling
curl -s "http://localhost:5002/api/matched-carriers-leads?state=OH&days=60&insurance_companies=Progressive&limit=5&month_based=true"
```

## Performance Metrics

### Working System Results
- **Database Size**: 383,510 total records
- **30-day Progressive filter**: ~239 leads (instead of constant 708)
- **Processing Time**: ~2-3 seconds for full database scan
- **Memory Usage**: Acceptable for 383K record processing

### Expected Scaling
- 30-day filter: Smaller subset
- 60-day filter: Larger subset (approximately 2x 30-day results)
- 90-day filter: Largest subset (approximately 3x 30-day results)

## Cache Management

### When to Update Cache Buster
Update the cache buster in `/var/www/vanguard/index.html` when modifying:
- `/var/www/vanguard/js/fcsma-api-override-v5.js`
- Any JavaScript logic affecting lead generation

### Current Version Format
```
v=YYYYMMDD_HHMM
Example: v=20251011_0153
```

## Data Structure

### API Response Format
```json
{
  "status": "success",
  "total_leads": 239,
  "processed_records": 383510,
  "data_source": "matched_carriers_20251009_183433.csv",
  "leads": [
    {
      "dot_number": "3738080",
      "mc_number": "MC1322159",
      "legal_name": "J & J ON THE MOVE LLC",
      "city": "TOLEDO",
      "state": "OH",
      "phone": "(419) 973-1493",
      "email_address": "ACE22590@GMAIL.COM",
      "insurance_carrier": "PROGRESSIVE PREFERRED INSURANCE CO.",
      "renewal_date": "2025-10-12",
      "renewal_date_formatted": "10/12/2025",
      "days_until_renewal": 1,
      "power_units": 1,
      "estimated_premium": 3500,
      "lead_score": 90
    }
  ]
}
```

### Insurance Company Mapping
The system includes smart mapping for common insurance companies:
- "Progressive" → "Progressive Preferred Insurance Company"
- "GEICO" → "GEICO"
- "Great West" → "Great West"
- "Canal" → "Canal"
- And more...

## Backup and Recovery

### Critical Files to Backup
1. `/var/www/vanguard/js/fcsma-api-override-v5.js`
2. `/var/www/vanguard/api/matched-carriers-leads.py`
3. `/var/www/vanguard/backend/server.js`
4. `/var/www/vanguard/index.html`
5. `/home/corp06/matched_carriers_20251009_183433.csv`

### Recovery Procedure
1. Restore backed up files
2. Restart services using commands above
3. Test API endpoints
4. Update cache buster if needed
5. Verify frontend functionality

## Known Working Configuration Summary

**Date**: October 11, 2025
**Status**: ✅ FULLY OPERATIONAL

**Key Version Numbers**:
- JavaScript Cache Buster: `v=20251011_0153`
- Python API: Port 5002 (Flask)
- Node.js Backend: Port 3001 (Express)
- API Limit: 5000 leads max
- Database: 383,510 records

**Confirmed Working Features**:
- ✅ Month-based insurance expiration filtering
- ✅ Multi-company selection (no more 0 results)
- ✅ Proper date scaling (30-day vs 60-day filters)
- ✅ Future-only dates (no past expiration dates)
- ✅ Full proxy chain functionality

## Contact & Support

For issues with this system:
1. Check service status using commands above
2. Review API logs for errors
3. Test direct API endpoints
4. Verify cache buster version
5. Restart services if needed

**Last Updated**: October 11, 2025
**System Status**: OPERATIONAL
**Next Review**: As needed for data updates or feature requests