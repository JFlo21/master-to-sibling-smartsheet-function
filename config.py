# config.py

# This configuration defines the synchronization rules from a source sheet
# to one or more target sheets using a stateful "append-if-not-exist" logic.
# This version corrects the column mappings to ensure all source columns
# originate from the single source sheet.

SHEET_CONFIG = {
    'source_sheet_id': 3733355007790980,  # <-- The "brain" sheet where all data originates.
    'targets': [
        {
            'id': 5723337641643908,          # <-- Your Target Sheet 1 ID.
            'description': 'One-Way Log Sheet for Project Data',
            'tracking_column_name': 'Source_Row_ID', 
            'column_id_mapping': {
                # Source Column ID (from brain sheet) : Target Column ID
                6922793410842500: 5180541294563204,
            }
        },
        {
            'id': 485894524981124,           # <-- Your Target Sheet 2 ID.
            'description': 'Second One-Way Log Sheet',
            'tracking_column_name': 'Source_Row_ID', 
            'column_id_mapping': {
                # CORRECTED: Uses the source column from the brain sheet.
                6922793410842500: 4526106084069252
            }
        },
        {
            'id': 2198406433820548,           # <-- Your Target Sheet 3 ID.
            'description': 'Third One-Way Log Sheet',
            'tracking_column_name': 'Source_Row_ID', 
            'column_id_mapping': {
                # Source Column ID (from brain sheet) : Target Column ID
                6922793410842500: 5243793911271300
            }
        },
        {
            'id': 7514584211476356,           # <-- Your Target Sheet 4 ID.
            'description': 'Fourth One-Way Log Sheet',
            'tracking_column_name': 'Source_Row_ID', 
            'column_id_mapping': {
                # Source Column ID (from brain sheet) : Target Column ID
                6922793410842500: 5604221820555140
            }
        },
        {
            'id': 6315205374988164,           # <-- Your Target Sheet 5 ID.
            'description': 'Fifth One-Way Log Sheet',
            'tracking_column_name': 'Source_Row_ID', 
            'column_id_mapping': {
                # Source Column ID (from brain sheet) : Target Column ID
                3784709278224260: 2910306835320708
            }
        }
    ]
}
