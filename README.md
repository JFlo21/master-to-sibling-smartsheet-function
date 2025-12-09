# master-to-sibling-smartsheet-function

Automated Smartsheet synchronization system supporting multi-source snapshot tracking with historical backfill capabilities.

## Features

- **Multi-Source Support**: Synchronize data from multiple source sheets
- **Snapshot Mode**: Create weekly point-in-time snapshots for historical tracking
- **Update Mode**: One-way synchronization for continuous updates
- **Historical Backfill**: Automatically fill missing snapshot rows for past weeks
- **Composite Tracking**: Track rows across multiple sources with unique identifiers
- **Batch Processing**: Handle large datasets with automatic batching (500 rows/batch)

## Configuration

### Historical Backfill Settings

Located in `config.py`:

```python
ENABLE_HISTORICAL_BACKFILL = True  # Set to False after initial backfill
HISTORICAL_BACKFILL_START = '2025-06-15'  # Start date for scanning historical weeks
```

### Multi-Source Configuration

The system supports multiple source sheets:

```python
'source_sheets': [
    {
        'id': 3733355007790980,
        'description': 'Primary Master Sheet',
        'work_request_column_id': 6922793410842500,
    },
    {
        'id': 6329947502104452,
        'description': 'Secondary Master Sheet',
        'work_request_column_id': 1509281497829252,
    },
]
```

### Target Sheet Configuration

Each target sheet has independent sync rules:

- **sync_mode**: `'snapshot'` or `'update'`
- **sync_start_date**: Earliest date to process (format: `'YYYY-MM-DD'`)
- **tracking_column_name**: Column used to track source rows
- **column_id_mapping**: Maps source columns to target columns
- **generated_columns**: Auto-populated fields (week_ending_date, week_number)

## How It Works

### Snapshot Mode

1. **Load Source Data**: Retrieves all rows from configured source sheets
2. **Generate Tracking IDs**: Creates composite IDs (`{source_sheet_id}_{row_id}`)
3. **Scan Existing Snapshots**: Identifies which week/row combinations already exist
4. **Identify Gaps**: Determines which weeks have incomplete snapshots
5. **Backfill Missing Rows**: Creates snapshot rows for missing week/source combinations
6. **Update Current Week**: Updates existing rows for the current week with latest data

### Historical Backfill Process

When `ENABLE_HISTORICAL_BACKFILL = True`:

1. Scans all weeks from `HISTORICAL_BACKFILL_START` to current week
2. For each week, compares expected rows (from all sources) vs existing rows
3. Creates missing snapshot rows in batches of 500
4. Logs progress showing `existing/total` counts per week

**Example Output:**
```
Week 2025-06-29: 150/253 rows exist - marking for backfill
Week 2025-07-06: 253/253 rows exist - Complete
```

### Update Mode

Traditional one-way sync that updates existing rows based on tracking ID.

## Usage

### Initial Setup

1. Configure source sheets in `config.py`
2. Set `ENABLE_HISTORICAL_BACKFILL = True`
3. Set `HISTORICAL_BACKFILL_START` to desired start date
4. Run the sync

### After Historical Backfill

1. Set `ENABLE_HISTORICAL_BACKFILL = False` in `config.py`
2. Script will only process current week going forward

### Running the Script

```bash
export SMARTSHEET_ACCESS_TOKEN="your_token_here"
python smartsheet_sync.py
```

### GitHub Actions

The workflow runs automatically every 15 minutes. You can also trigger it manually from the Actions tab.

## Expected Behavior

For each week ending date, **EVERY** Work Request # from **ALL** source sheets will have a corresponding snapshot row in each target sheet.

**Example:**
- Primary source: 253 rows
- Secondary source: 50 rows
- Total expected per week: 303 rows

Each target sheet will have 303 rows per week (one for each Work Request # across all sources).

## Important Notes

1. **First Run**: With historical backfill enabled, the first run may create thousands of rows
2. **API Limits**: Script respects Smartsheet API limits with batch processing
3. **Existing Data**: Existing snapshot rows are never modified (except current week)
4. **Composite Keys**: Tracking IDs use format `{source_sheet_id}_{row_id}` for uniqueness

## Troubleshooting

### Missing Rows

If snapshots are incomplete, check:
- `ENABLE_HISTORICAL_BACKFILL` is set to `True`
- `HISTORICAL_BACKFILL_START` covers the desired date range
- Source sheet IDs and column IDs are correct

### Performance

For large datasets:
- Processing occurs in batches of 500 rows
- Monitor API rate limits
- Check GitHub Actions logs for progress

## Configuration Reference

### Target Sheet Order (Snapshot Mode)

1. **Primary**: 2198406433820548 (Start: 2025-06-29)
2. **Secondary**: 2894503242321796 (Start: 2025-09-07)
3. **Tertiary**: 6620020097372036 (Start: 2025-10-05)
4. **Quaternary**: 5477191610486660 (Start: 2025-10-19)
5. **Quinary**: 8891640346267524 (Start: 2025-10-31)

Each sheet processes data from its start date onwards indefinitely.
