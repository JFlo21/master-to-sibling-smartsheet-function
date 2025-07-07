# config.py

# This configuration has been updated with a more robust structure for handling
# script-generated values like dates and week numbers.

SHEET_CONFIG = {
    'source_sheet_id': 3733355007790980,
    'targets': [
        {
            'id': 5723337641643908,
            'description': 'Weekly Snapshot Log 1',
            'sync_mode': 'snapshot',
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
            'id': 2198406433820548,
            'description': 'Third One-Way Log Sheet (Weekly Snapshot)',
            'sync_mode': 'snapshot',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                # This section now only contains direct source-to-target mappings.
                6922793410842500: 5243793911271300,
            },
            # NEW SECTION: This explicitly defines columns with script-generated values.
            'generated_columns': {
                'week_ending_date': 740194283900804,  # Target Column ID for the date
                'week_number': 5717692373487492,     # Target Column ID for the week number
            }
        },
        {
            'id': 7514584211476356,
            'description': 'Fourth One-Way Log Sheet',
            'sync_mode': 'update',
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                6922793410842500: 5604221820555140
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
        }
    ]
}
