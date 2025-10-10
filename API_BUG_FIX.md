# API Bug Fix: Insurance Company Filtering

## Issue
When filtering for OH state + Progressive insurance + 30 days expiration, the system returned 0 leads despite having 4,105 Progressive carriers in Ohio.

## Root Cause Analysis

### Problem 1: Exact Match vs Partial Match
The API was using `IN` clause for exact matching:
```sql
AND insurance_company_name IN (?)
```

But Progressive has multiple company names:
- PROGRESSIVE PREFERRED INSURANCE CO.
- PROGRESSIVE NORTHERN INSURANCE COMPANY
- PROGRESSIVE SOUTHEASTERN INSURANCE COMPANY
- PROGRESSIVE CASUALTY INSURANCE COMPANY
- PROGRESSIVE EXPRESS INSURANCE COMPANY
- PROGRESSIVE COUNTY MUTUAL
- etc.

### Problem 2: Overly Restrictive Date Filtering
The API required `days_until_expiry > 0`, excluding recently expired policies that might still be renewable.

## Solution Applied

### Fix 1: Partial Match for Insurance Companies
Changed from exact matching to partial matching:

**Before:**
```sql
AND insurance_company_name IN (?)
```

**After:**
```sql
AND (insurance_company_name LIKE ? OR insurance_company_name LIKE ? ...)
```

This allows searching for "Progressive" to match all Progressive companies.

### Fix 2: Include Recently Expired Policies
Added 90-day lookback for expired policies:

**Before:**
```sql
AND days_until_expiry > 0
AND days_until_expiry <= ?
```

**After:**
```sql
AND days_until_expiry <= ?
AND days_until_expiry >= -90
```

This includes policies expired within 90 days (still potentially renewable).

## Results

**OH + Progressive + 30 days:**
- Before fix: 0 leads
- After fix: 708 leads

## Files Modified

**Vanguard API File:** `/home/corp06/vanguard-vps-package/api_complete.py`

**Modified Function:** `get_expiring_insurance_leads()`

**Lines Changed:** 396-405 (insurance company filtering) and 382-383 (date filtering)

## Testing

```sql
-- Test query that now works
SELECT COUNT(*) FROM fmcsa_enhanced
WHERE state = 'OH'
AND insurance_company_name LIKE '%PROGRESSIVE%'
AND days_until_expiry <= 30
AND days_until_expiry >= -90;
-- Result: 708 carriers
```

## Deployment

The fix has been applied to the main Vanguard API file. Restart the API server for changes to take effect:

```bash
# Restart Vanguard API
cd /home/corp06/vanguard-vps-package
python3 api_complete.py
```

## Impact

This fix resolves the filtering issue and will now properly return leads for:
- Partial insurance company name matches
- Multi-company insurance groups (Progressive, United Financial, etc.)
- Recently expired policies that are still actionable for renewal