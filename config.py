# config.py

# ============================================================================
# SMARTSHEET SYNCHRONIZATION CONFIGURATION
# ============================================================================
# This configuration defines the source sheet and all target sheets for
# the Master-to-Sibling Smartsheet synchronization function.
#
# ARCHITECTURE OVERVIEW:
# - source_sheets: Array of source Smartsheet configurations (multi-source support)
# - source_sheet_id: Legacy single source (maintained for backward compatibility)
# - targets: Array of target sheet configurations with independent sync rules
#
# SYNC MODES:
# - 'update': Performs one-way synchronization that updates existing rows
#             based on the tracking column identifier
# - 'snapshot': Creates weekly point-in-time records for historical tracking
#
# DATE FILTERING STRATEGY:
# - sync_start_date: Inclusive start date (YYYY-MM-DD format)
#                    Only records from this date forward will be processed
# - sync_end_date: DEPRECATED - Not used in current architecture
#                  All sheets run concurrently based on start dates only
#
# COLUMN MAPPING CONVENTIONS:
# - Numeric values: Direct Smartsheet column IDs (legacy approach)
# - String values: Column names resolved at runtime (recommended for flexibility)
# - The script dynamically resolves column names to IDs during execution
#
# GENERATED COLUMNS:
# - week_ending_date: Calculated field for weekly snapshot grouping
# - week_number: ISO week number for temporal indexing and reporting
#
# HISTORICAL BACKFILL CONFIGURATION:
# - ENABLE_HISTORICAL_BACKFILL: Set to True to fill missing historical snapshot rows
#                                Set to False after initial backfill is complete
# - HISTORICAL_BACKFILL_START: Start date for scanning historical weeks
#                               Scans all weeks from this date to current week
# ============================================================================

# Historical Backfill Settings
ENABLE_HISTORICAL_BACKFILL = True
HISTORICAL_BACKFILL_START = '2025-06-15'

SHEET_CONFIG = {
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
    ],
    # Legacy support: keep source_sheet_id for update mode targets
    'source_sheet_id': 3733355007790980,
    'targets': [
        # ====================================================================
        # UPDATE MODE TARGETS
        # One-Way Synchronization Logs - Continuous Update Pattern
        # ====================================================================
        {
            'id': 5723337641643908,
            'description': 'Weekly Snapshot Log 1',
            'sync_mode': 'update',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                6922793410842500: 5180541294563204,
            },
            # NOTE: To enable full snapshotting capabilities, add a 'generated_columns'
            # section here similar to the snapshot target sheet configurations below.
        },
        {
            'id': 485894524981124,
            'description': 'Second One-Way Log Sheet',
            'sync_mode': 'update',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                6922793410842500: 4526106084069252,
            }
        },
        {
            'id': 6315205374988164,
            'description': 'Fifth One-Way Log Sheet',
            'sync_mode': 'update',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                1865904432041860: 2910306835320708
            }
        },
        
        # ====================================================================
        # SNAPSHOT MODE TARGETS
        # Weekly Point-in-Time Historical Data Capture
        # ====================================================================
        # All snapshot targets run concurrently based on their start dates.
        # Each sheet independently filters data from its configured start date.
        # This allows for parallel historical tracking across multiple sheets.
        # ====================================================================
        
        # PRIMARY TARGET SHEET - Earliest start date
        # NOTE: This sheet was previously configured with start date 2025-09-07
        # Changed to 2025-06-29 to enable historical backfill per business requirements
        # Ensure source data is available for the earlier date range
        {
            'id': 2198406433820548,
            'description': 'Primary Target Sheet (Weekly Snapshot)',
            'sync_mode': 'snapshot',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                # Map source "Work Request #" to target "Work Request #"
                6922793410842500: 5243793911271300,
            },
            # Columns populated by script-generated calculated values
            'generated_columns': {
                'week_ending_date': 740194283900804,   # Target "Week Ending Date" column
                'week_number': 5717692373487492,       # Target "Week Number" column
            },
            # DATE FILTER: Independent start date - no end date
            # This sheet processes all data from 06/29/2025 onwards indefinitely
            'sync_start_date': '2025-06-29',
            'target_work_request_column': 5243793911271300,  # Explicit target column ID
        },
        # SECONDARY TARGET SHEET
        {
            'id': 2894503242321796,
            'description': 'Secondary Target Sheet (Weekly Snapshot)',
            'sync_mode': 'snapshot',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                # Map source "Work Request #" to target "Work Request #"
                6922793410842500: 6811704037691268,
            },
            # Columns populated by script-generated calculated values
            'generated_columns': {
                'week_ending_date': 2308104410320772,  # Target "Week Ending Date" column
                'week_number': 8957950735110020,       # Target "Week Number" column
            },
            # DATE FILTER: Independent start date - no end date
            # This sheet processes all data from 09/07/2025 onwards indefinitely
            'sync_start_date': '2025-09-07',
            'target_work_request_column': 6811704037691268,  # Explicit target column ID
        },
        # TERTIARY TARGET SHEET
        {
            'id': 6620020097372036,
            'description': 'Tertiary Target Sheet (Weekly Snapshot) — Active 2025-10-05+',
            'sync_mode': 'snapshot',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                # Map source "Work Request #" to target column by name
                # Runtime resolution allows for greater flexibility
                6922793410842500: 'Work Request #',
            },
            # Columns populated by script-generated calculated values (resolved by name)
            'generated_columns': {
                'week_ending_date': 'Week Ending Date',
                'week_number': 'Week Number',
            },
            # DATE FILTER: Independent start date - no end date
            # This sheet processes all data from 10/05/2025 onwards indefinitely
            'sync_start_date': '2025-10-05'
        },
        # QUATERNARY TARGET SHEET
        {
            'id': 5477191610486660,
            'description': 'Quaternary Target Sheet (Weekly Snapshot) — Active 2025-10-19+',
            'sync_mode': 'snapshot',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                # Map source "Work Request #" to target column by name
                # Runtime resolution allows for greater flexibility
                6922793410842500: 'Work Request #',
            },
            # Columns populated by script-generated calculated values (resolved by name)
            'generated_columns': {
                'week_ending_date': 'Week Ending Date',
                'week_number': 'Week Number',
            },
            # DATE FILTER: Independent start date - no end date
            # This sheet processes all data from 10/19/2025 onwards indefinitely
            'sync_start_date': '2025-10-19'
        },
        # QUINARY TARGET SHEET
        {
            'id': 8891640346267524,
            'description': 'Quinary Target Sheet (Weekly Snapshot) — Active 2025-10-31+',
            'sync_mode': 'snapshot',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                # Map source "Work Request #" to target "Work Request #"
                # Using column name for runtime resolution (recommended pattern)
                6922793410842500: 'Work Request #',
            },
            # Columns populated by script-generated calculated values (resolved by name)
            # These values are computed during sync execution based on temporal logic
            'generated_columns': {
                'week_ending_date': 'Week Ending Date',  # ISO week ending date calculation
                'week_number': 'Week Number',             # ISO 8601 week number
            },
            # DATE FILTER: Independent start date - no end date
            # This sheet processes all data from 10/31/2025 onwards indefinitely
            # Runs concurrently with other snapshot sheets based on date filtering
            'sync_start_date': '2025-10-31'
        },
    ]
}
