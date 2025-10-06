# config.py

# This configuration has been updated with a more robust structure for handling
# script-generated values like dates and week numbers.

SHEET_CONFIG = {
    'source_sheet_id': 3733355007790980,
    'targets': [
        {
            'id': 5723337641643908,
            'description': 'Weekly Snapshot Log 1',
            'sync_mode': 'update',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                6922793410842500: 5180541294563204,
            },
            # NOTE: To enable full snapshotting, add a 'generated_columns' section here
            # similar to the one in the third target sheet configuration below.
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
            'id': 2894503242321796,
            'description': 'Primary Target Sheet (Weekly Snapshot)',
            'sync_mode': 'snapshot',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                # Map source "Work Request #" to target "Work Request #"
                6922793410842500: 6811704037691268,
            },
            # NEW SECTION: This explicitly defines columns with script-generated values.
            'generated_columns': {
                'week_ending_date': 2308104410320772,  # Target "Week Ending Date" column
                'week_number': 8957950735110020,       # Target "Week Number" column
            },
            # DATE FILTER: Only sync data from this date onwards
            'sync_start_date': '2025-09-07'  # Only sync data from 09/07/2025 onwards
        },
        {
            'id': 2198406433820548,
            'description': 'Secondary Target Sheet (Weekly Snapshot - Duplicate)',
            'sync_mode': 'snapshot',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                # Map source "Work Request #" to target "Work Request #"
                6922793410842500: 5243793911271300,
            },
            # NEW SECTION: This explicitly defines columns with script-generated values.
            'generated_columns': {
                'week_ending_date': 740194283900804,   # Target "Week Ending Date" column
                'week_number': 5717692373487492,       # Target "Week Number" column
            },
            # DATE FILTERS: Active for this target from start to end dates
            'sync_start_date': '2025-09-07',  # Only sync data from 09/07/2025 onwards
            'sync_end_date': '2025-10-04'     # Sunset on 10/04/2025 so a new sheet takes over 10/05
        },
        {
            'id': 6620020097372036,
            'description': 'Secondary Target Sheet (Weekly Snapshot - Duplicate) — Active 2025-10-05+',
            'sync_mode': 'snapshot',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                # Map source "Work Request #" to target column by name in the new sheet
                6922793410842500: 'Work Request #',
            },
            # NEW SECTION: Columns with script-generated values (resolved by name)
            'generated_columns': {
                'week_ending_date': 'Week Ending Date',
                'week_number': 'Week Number',
            },
            # DATE FILTER: New secondary sheet becomes active starting 10/05/2025
            'sync_start_date': '2025-10-05'
        },
        {
            'id': 6315205374988164,
            'description': 'Fifth One-Way Log Sheet',
            'sync_mode': 'update',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                1865904432041860: 2910306835320708
            }
        }
    ]
}
