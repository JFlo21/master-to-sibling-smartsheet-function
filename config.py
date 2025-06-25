# config.py

# This configuration defines the synchronization rules from a source sheet
# to one or more target sheets using a stateful "append-if-not-exist" logic.
# This is where you will manage all your sheet and column mappings.

SHEET_CONFIG = {
    'source_sheet_id': 3733355007790980,  # <-- The "brain" sheet where all data originates.
    'targets': [
        {
            'id': 5723337641643908,          # <-- Your Target Sheet 1 ID.
            'description': 'One-Way Log Sheet for Project Data',
            
            # This is the name of the new column you manually added to your target sheet.
            # It's used to track which rows have already been copied.
            'tracking_column_name': 'Source_Row_ID', 
            
            # Defines which source column IDs map to which target column IDs.
            # This method is robust and won't break if column names change.
            'column_id_mapping': {
                # Source Column ID : Target Column ID
                6922793410842500: 5180541294563204,
            }
        },
        {
            'id': 485894524981124,           # <-- Your Target Sheet 2 ID.
            'description': 'Second One-Way Log Sheet',
            
            # REMINDER: You must add a column with this exact name to your new target sheet.
            'tracking_column_name': 'Source_Row_ID', 
            
            'column_id_mapping': {
                # Source Column ID : Target Column ID
                6922793410842500: 4526106084069252
            }
        },
        {
            'id': 2198406433820548,           # <-- Your Target Sheet 3 ID.
            'description': 'Third One-Way Log Sheet',
            
            # REMINDER: You must add a column with this exact name to your new target sheet.
            'tracking_column_name': 'Source_Row_ID', 
            
            'column_id_mapping': {
                # New Mapping for the third sheet.
                # Source Column ID : Target Column ID
                692279341082500: 5243793911271300
            }
        },
        {
            'id': 7514584211476356,           # <-- Your Target Sheet 4 ID.
            'description': 'Fourth One-Way Log Sheet',
            
            # REMINDER: You must add a column with this exact name to your new target sheet.
            'tracking_column_name': 'Source_Row_ID', 
            
            'column_id_mapping': {
                # New Mapping for the fourth sheet.
                # Source Column ID : Target Column ID
                6922793410842500: 5604221820555140
            }
        },
        {
            'id': 6315205374988164,           # <-- Your NEW Target Sheet 5 ID.
            'description': 'Fifth One-Way Log Sheet',
            
            # REMINDER: You must add a column with this exact name to your new target sheet.
            'tracking_column_name': 'Source_Row_ID', 
            
            'column_id_mapping': {
                # New Mapping for the fifth sheet.
                # Source Column ID : Target Column ID
                1865904432041860: 2910306835320708
            }
        }
    ]
}
