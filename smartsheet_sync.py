# smartsheet_sync.py

import os
import smartsheet
from config import SHEET_CONFIG

def get_column_map_by_name(sheet):
    """Creates a mapping of column names to column IDs for a given sheet for easy lookup."""
    return {column.title: column.id for column in sheet.columns}

def get_existing_tracking_ids(smart, sheet, tracking_column_id):
    """
    Efficiently fetches all unique values from the tracking column in a sheet.
    This creates a set of IDs for fast checking, avoiding repeated API calls.
    """
    existing_ids = set()
    # The 'include' and 'column_ids' parameters are powerful optimizers.
    # They tell the Smartsheet API to only send back the data we absolutely need.
    for row in smart.Sheets.get_sheet(sheet.id, include=['data'], column_ids=[tracking_column_id]).rows:
        # Check if the cell has a value before adding to the set.
        if row.cells[0].value:
            existing_ids.add(row.cells[0].value)
    return existing_ids

def process_stateful_sync(smart, config):
    """
    Main function to perform a one-way, stateful sync (append-if-not-exist)
    from a source sheet to multiple target sheets. It will not re-implement or delete data.
    """
    source_sheet_id = config['source_sheet_id']
    print("--- Starting Stateful Sync Process ---")
    print(f"Fetching source sheet: {source_sheet_id}")

    # 1. Load the source sheet.
    try:
        source_sheet = smart.Sheets.get_sheet(source_sheet_id)
        print(f"Successfully loaded source sheet: '{source_sheet.name}' with {len(source_sheet.rows)} rows.")
    except Exception as e:
        print(f"FATAL ERROR: Could not load source sheet ID {source_sheet_id}. Halting execution. Error: {e}")
        return

    # 2. Iterate through each target sheet configuration defined in config.py.
    for target_config in config['targets']:
        target_sheet_id = target_config['id']
        tracking_col_name = target_config['tracking_column_name']
        column_mapping = target_config['column_id_mapping']
        
        print(f"\nProcessing target: '{target_config['description']}' (ID: {target_sheet_id})")

        # 3. Load the target sheet and verify the crucial tracking column exists.
        try:
            target_sheet = smart.Sheets.get_sheet(target_sheet_id)
            target_column_map = get_column_map_by_name(target_sheet)
            print(f"Successfully loaded target sheet: '{target_sheet.name}'")

            if tracking_col_name not in target_column_map:
                print(f"ERROR: The essential tracking column '{tracking_col_name}' was not found in target sheet '{target_sheet.name}'. Skipping this target.")
                continue
            
            tracking_column_id = target_column_map[tracking_col_name]
        except Exception as e:
            print(f"ERROR: Could not load or process target sheet ID {target_sheet_id}. Skipping. Error: {e}")
            continue

        # 4. Get all source row IDs that have already been copied to the target.
        # This is the core of the "don't re-implement" logic.
        existing_ids = get_existing_tracking_ids(smart, target_sheet, tracking_column_id)
        print(f"Found {len(existing_ids)} rows already logged in the target sheet.")

        # 5. Identify which rows from the source are new and need to be copied.
        rows_to_add = []
        for source_row in source_sheet.rows:
            # Check if the source row's unique ID is NOT in the set of IDs we found on the target.
            if source_row.id not in existing_ids:
                # This row is new! Prepare it for copying.
                new_row = smartsheet.models.Row()
                new_row.to_top = True  # Add new rows to the top. Use to_bottom=True to add to the bottom.

                # Map cells based on the column_id_mapping from the config file.
                for source_col_id, target_col_id in column_mapping.items():
                    source_cell = source_row.get_column(source_col_id)
                    # We only create a cell if the source cell has a value.
                    if source_cell and source_cell.value is not None:
                        new_cell = smartsheet.models.Cell()
                        new_cell.column_id = target_col_id
                        new_cell.value = source_cell.value
                        new_cell.strict = False
                        new_row.cells.append(new_cell)
                
                # IMPORTANT: Add the source row's ID to the tracking column in the new row.
                tracking_cell = smartsheet.models.Cell()
                tracking_cell.column_id = tracking_column_id
                tracking_cell.value = source_row.id
                tracking_cell.strict = False
                new_row.cells.append(tracking_cell)

                rows_to_add.append(new_row)

        # 6. Add the newly built rows to the target sheet in a single API call.
        if rows_to_add:
            print(f"Found {len(rows_to_add)} new rows to add. Adding to target sheet...")
            try:
                smart.Sheets.add_rows(target_sheet_id, rows_to_add)
                print(f"Successfully added {len(rows_to_add)} new rows.")
            except Exception as e:
                print(f"ERROR: Failed to add new rows to target sheet ID {target_sheet_id}. Error: {e}")
        else:
            print("No new rows to add. Target sheet is already up-to-date.")

    print("\n--- Stateful Sync Process Complete ---")


if __name__ == '__main__':
    # This securely gets the API token from the GitHub Actions secrets.
    access_token = os.getenv('SMARTSHEET_ACCESS_TOKEN')
    if not access_token:
        raise ValueError("FATAL ERROR: SMARTSHEET_ACCESS_TOKEN environment variable not found.")

    # Initialize the Smartsheet client.
    smartsheet_client = smartsheet.Smartsheet(access_token)
    smartsheet_client.errors_as_exceptions(True)
    
    # Run the main sync process.
    process_stateful_sync(smartsheet_client, SHEET_CONFIG)

