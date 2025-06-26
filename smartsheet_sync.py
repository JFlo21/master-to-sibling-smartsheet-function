# smartsheet_sync.py

import os
import smartsheet
from config import SHEET_CONFIG

def get_column_map_by_name(sheet):
    """Creates a mapping of column names to column IDs for a given sheet for easy lookup."""
    return {column.title: column.id for column in sheet.columns}

def get_target_row_map(smart, sheet, tracking_column_id):
    """
    Fetches all rows from the target sheet and creates a dictionary that maps
    the source row ID (from the tracking column) to the entire target row object.
    This allows for quick lookup and cell value comparison.
    """
    target_map = {}
    for row in sheet.rows:
        tracking_cell = row.get_column(tracking_column_id)
        if tracking_cell and tracking_cell.value:
            # Key: Source Row ID, Value: The entire Target Row object
            target_map[tracking_cell.value] = row
    return target_map

def process_stateful_sync_with_updates(smart, config):
    """
    Main function to perform a one-way sync that ADDS new rows and UPDATES existing rows.
    """
    source_sheet_id = config['source_sheet_id']
    print("--- Starting Sync Process with Update Logic ---")
    print(f"Fetching source sheet: {source_sheet_id}")

    try:
        source_sheet = smart.Sheets.get_sheet(source_sheet_id)
        print(f"Successfully loaded source sheet: '{source_sheet.name}' with {len(source_sheet.rows)} rows.")
    except Exception as e:
        print(f"FATAL ERROR: Could not load source sheet ID {source_sheet_id}. Halting execution. Error: {e}")
        return

    for target_config in config['targets']:
        target_sheet_id = target_config['id']
        tracking_col_name = target_config['tracking_column_name']
        column_mapping = target_config['column_id_mapping']
        
        print(f"\nProcessing target: '{target_config['description']}' (ID: {target_sheet_id})")

        try:
            target_sheet = smart.Sheets.get_sheet(target_sheet_id)
            target_column_map_by_name = get_column_map_by_name(target_sheet)
            print(f"Successfully loaded target sheet: '{target_sheet.name}'")

            if tracking_col_name not in target_column_map_by_name:
                print(f"ERROR: Tracking column '{tracking_col_name}' not found in target sheet. Skipping.")
                continue
            
            tracking_column_id = target_column_map_by_name[tracking_col_name]
        except Exception as e:
            print(f"ERROR: Could not load or process target sheet ID {target_sheet_id}. Skipping. Error: {e}")
            continue

        target_row_map = get_target_row_map(smart, target_sheet, tracking_column_id)
        print(f"Found {len(target_row_map)} existing rows to check for updates.")

        rows_to_add = []
        rows_to_update = []

        for source_row in source_sheet.rows:
            if source_row.id in target_row_map:
                # --- UPDATE LOGIC ---
                # This row exists in the target, so we check if any values have changed.
                target_row = target_row_map[source_row.id]
                row_to_update = smartsheet.models.Row()
                row_to_update.id = target_row.id
                
                has_changed = False
                for source_col_id, target_col_id in column_mapping.items():
                    source_cell = source_row.get_column(source_col_id)
                    target_cell = target_row.get_column(target_col_id)
                    
                    # Normalize values to handle cases where a cell might be None
                    source_value = source_cell.value if source_cell else None
                    target_value = target_cell.value if target_cell else None

                    if source_value != target_value:
                        has_changed = True
                        updated_cell = smartsheet.models.Cell()
                        updated_cell.column_id = target_col_id
                        updated_cell.value = source_value
                        updated_cell.strict = False
                        row_to_update.cells.append(updated_cell)

                if has_changed:
                    rows_to_update.append(row_to_update)

            else:
                # --- ADD LOGIC (Same as before) ---
                # This row is new and needs to be added to the target sheet.
                new_row = smartsheet.models.Row()
                new_row.to_top = True

                for source_col_id, target_col_id in column_mapping.items():
                    source_cell = source_row.get_column(source_col_id)
                    if source_cell and source_cell.value is not None:
                        new_cell = smartsheet.models.Cell()
                        new_cell.column_id = target_col_id
                        new_cell.value = source_cell.value
                        new_cell.strict = False
                        new_row.cells.append(new_cell)
                
                tracking_cell = smartsheet.models.Cell()
                tracking_cell.column_id = tracking_column_id
                tracking_cell.value = source_row.id
                new_row.cells.append(tracking_cell)
                rows_to_add.append(new_row)

        # --- BATCH OPERATIONS ---
        # Perform updates and additions in bulk for efficiency.
        if rows_to_update:
            print(f"Found {len(rows_to_update)} rows with changes. Updating...")
            try:
                smart.Sheets.update_rows(target_sheet_id, rows_to_update)
                print("Successfully updated rows.")
            except Exception as e:
                print(f"ERROR during row update: {e}")
        else:
            print("No updates needed for existing rows.")

        if rows_to_add:
            print(f"Found {len(rows_to_add)} new rows to add. Adding...")
            try:
                smart.Sheets.add_rows(target_sheet_id, rows_to_add)
                print("Successfully added new rows.")
            except Exception as e:
                print(f"ERROR during row addition: {e}")
        else:
            print("No new rows to add.")

    print("\n--- Sync Process Complete ---")

if __name__ == '__main__':
    access_token = os.getenv('SMARTSHEET_ACCESS_TOKEN')
    if not access_token:
        raise ValueError("FATAL ERROR: SMARTSHEET_ACCESS_TOKEN environment variable not found.")

    smartsheet_client = smartsheet.Smartsheet(access_token)
    smartsheet_client.errors_as_exceptions(True)
    process_stateful_sync_with_updates(smartsheet_client, SHEET_CONFIG)
