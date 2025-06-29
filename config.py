# config.py

# This configuration has been updated to support two different sync modes:
# 'update': The original logic that adds new rows and updates existing ones.
# 'snapshot': The new logic that creates a new row for each source row every week.

SHEET_CONFIG = {
    'source_sheet_id': 3733355007790980,
    'targets': [
        {
            # --- THIS SHEET WILL USE THE NEW SNAPSHOT LOGIC ---
            'id': 5723337641643908,
            'description': 'Weekly Snapshot Log 1',
            'sync_mode': 'snapshot', # <-- New setting to control logic
            'tracking_column_name': 'Source_Row_ID',
            'week_ending_date_col_name': 'Week Ending Date', # <-- Name of the new date column
            'week_number_col_name': 'Week Number',         # <-- Name of the new week number column
            'column_id_mapping': {
                6922793410842500: 5180541294563204,
                # NOTE: This sheet needs its own date/week number columns and mappings
                # if you want to use the snapshot feature here fully.
            }
        },
        {
            # --- THIS SHEET IS NOW BACK TO THE STANDARD UPDATE LOGIC ---
            'id': 485894524981124,
            'description': 'Second One-Way Log Sheet',
            'sync_mode': 'update', # <-- Reverted to update mode
            'tracking_column_name': 'Source_Row_ID',
            'column_id_mapping': {
                6922793410842500: 4526106084069252,
            }
        },
        {
            # --- THIS SHEET WILL NOW USE THE SNAPSHOT LOGIC WITH THE CORRECT MAPPINGS ---
            'id': 2198406433820548,
            'description': 'Third One-Way Log Sheet (Weekly Snapshot)',
            'sync_mode': 'snapshot', # <-- Changed to snapshot mode
            'tracking_column_name': 'Source_Row_ID',
            'week_ending_date_col_name': 'Week Ending Date', # <-- Added for snapshot mode
            'week_number_col_name': 'Week Number',         # <-- Added for snapshot mode
            'column_id_mapping': {
                692279341082500: 5243793911271300,
                # Mappings have been moved here from the previous sheet.
                None: 740194283900804,  # Week Ending Date Target Column
                None: 5717692373487492,  # Week Number Target Column
            }
        },
        {
            # --- These sheets will continue using the original 'update' logic ---
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
