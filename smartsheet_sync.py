# smartsheet_sync.py

import os
import smartsheet
from config import SHEET_CONFIG
from datetime import datetime, date, timedelta

# --- NEW HELPER FUNCTIONS FOR DATE CALCULATIONS ---

def get_current_week_ending_date():
    """Calculates the upcoming Sunday as the 'Week Ending Date'."""
    today = date.today()
    # weekday() returns 0 for Monday and 6 for Sunday.
    # The calculation finds how many days to add to get to the next Sunday.
    days_until_sunday = (6 - today.weekday() + 7) % 7
    return today + timedelta(days=days_until_sunday)

def calculate_week_number(current_wed, start_date_str='2025-06-15'):
    """Calculates the week number based on a start date, where the start date is Week 0."""
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    delta_days = (current_wed - start_date).days
    # Integer division by 7 gives the number of full weeks passed.
    return delta_days // 7

# --- EXISTING HELPER FUNCTIONS ---

def get_column_map_by_name(sheet):
    """Creates a mapping of column names to column IDs for a given sheet for easy lookup."""
    return {column.title: column.id for column in sheet.columns}

def get_target_row_map_for_update(smart, sheet, tracking_column_id):
    """Fetches rows and maps source_id to the entire target row object for the 'update' mode."""
    target_map = {}
    for row in sheet.rows:
        tracking_cell = row.get_column(tracking_column_id)
        if tracking_cell and tracking_cell.value:
            target_map[tracking_cell.value] = row
    return target_map

def get_target_composite_keys_for_snapshot(smart, sheet, tracking_col_id, week_end_col_id):
    """
    Fetches rows and creates a set of composite keys (source_id, week_ending_date_str)
    for the 'snapshot' mode to prevent weekly duplicates.
    """
    composite_keys = set()
    for row in sheet.rows:
        tracking_cell = row.get_column(tracking_col_id)
        week_end_cell = row.get_column(week_end_col_id)
        if tracking_cell and tracking_cell.value and week_end_cell and week_end_cell.value:
            # The key is a tuple of the source row ID and the date string (e.g., '2025-07-06')
            composite_keys.add((tracking_cell.value, week_end_cell.value))
    return composite_keys

# --- NEW LOGIC HANDLERS ---

def handle_snapshot_sync(smart, source_sheet, target_config):
    """Handles the new time-series snapshot logic."""
    target_sheet_id = target_config['id']
    target_sheet = smart.Sheets.get_sheet(target_sheet_id)
    target_col_map = get_column_map_by_name(target_sheet)

    # Get IDs for the special columns needed for this mode
    tracking_col_id = target_col_map[target_config['tracking_column_name']]
    week_end_col_id = target_config['column_id_mapping'][None] # Using None as key for generated values
    week_num_col_id = target_config['column_id_mapping'][None] # Assuming order is consistent

    # Get current date info for this run
    current_wed = get_current_week_ending_date()
    current_week_num = calculate_week_number(current_wed)
    current_wed_str = current_wed.strftime('%Y-%m-%d')

    print(f"Current Week Ending Date: {current_wed_str} (Week {current_week_num})")
    
    existing_keys = get_target_composite_keys_for_snapshot(smart, target_sheet, tracking_col_id, week_end_col_id)
    print(f"Found {len(existing_keys)} existing snapshot entries in target.")

    rows_to_add = []
    for source_row in source_sheet.rows:
        composite_key = (source_row.id, current_wed_str)
        if composite_key not in existing_keys:
            # This is a new snapshot for this source row for this week.
            new_row = smartsheet.models.Row()
            new_row.to_bottom = True # Add snapshots to the bottom to maintain order
            
            # 1. Add mapped data from source
            for source_col_id, target_col_id in target_config['column_id_mapping'].items():
                if source_col_id is not None: # Skip the generated value mappings
                    source_cell = source_row.get_column(source_col_id)
                    if source_cell and source_cell.value is not None:
                        new_cell = smartsheet.models.Cell()
                        new_cell.column_id = target_col_id
                        new_cell.value = source_cell.value
                        new_row.cells.append(new_cell)
            
            # 2. Add the tracking ID
            new_row.cells.append(smartsheet.models.Cell({'column_id': tracking_col_id, 'value': source_row.id}))
            
            # 3. Add the generated Week Ending Date
            new_row.cells.append(smartsheet.models.Cell({'column_id': week_end_col_id, 'value': current_wed_str}))
            
            # 4. Add the generated Week Number
            new_row.cells.append(smartsheet.models.Cell({'column_id': week_num_col_id, 'value': current_week_num}))

            rows_to_add.append(new_row)

    if rows_to_add:
        print(f"Creating {len(rows_to_add)} new snapshot rows...")
        smart.Sheets.add_rows(target_sheet_id, rows_to_add)
        print("Successfully created snapshot rows.")
    else:
        print("No new snapshot rows to create for this week.")


def handle_update_sync(smart, source_sheet, target_config):
    """Handles the original add-or-update logic."""
    target_sheet_id = target_config['id']
    target_sheet = smart.Sheets.get_sheet(target_sheet_id)
    target_col_map = get_column_map_by_name(target_sheet)
    tracking_col_id = target_col_map[target_config['tracking_column_name']]
    column_mapping = target_config['column_id_mapping']
    
    target_row_map = get_target_row_map_for_update(smart, target_sheet, tracking_col_id)
    print(f"Found {len(target_row_map)} existing rows to check for updates.")

    rows_to_add, rows_to_update = [], []
    for source_row in source_sheet.rows:
        if source_row.id in target_row_map:
            target_row = target_row_map[source_row.id]
            row_to_update = smartsheet.models.Row({'id': target_row.id, 'cells': []})
            has_changed = False
            for src_id, tgt_id in column_mapping.items():
                src_val = (source_row.get_column(src_id).value if source_row.get_column(src_id) else None)
                tgt_val = (target_row.get_column(tgt_id).value if target_row.get_column(tgt_id) else None)
                if src_val != tgt_val:
                    has_changed = True
                    row_to_update.cells.append(smartsheet.models.Cell({'column_id': tgt_id, 'value': src_val}))
            if has_changed:
                rows_to_update.append(row_to_update)
        else:
            new_row = smartsheet.models.Row({'to_top': True, 'cells': []})
            for src_id, tgt_id in column_mapping.items():
                src_cell = source_row.get_column(src_id)
                if src_cell and src_cell.value is not None:
                    new_row.cells.append(smartsheet.models.Cell({'column_id': tgt_id, 'value': src_cell.value}))
            new_row.cells.append(smartsheet.models.Cell({'column_id': tracking_col_id, 'value': source_row.id}))
            rows_to_add.append(new_row)

    if rows_to_update:
        print(f"Found {len(rows_to_update)} rows with changes. Updating...")
        smart.Sheets.update_rows(target_sheet_id, rows_to_update)
        print("Successfully updated rows.")
    else:
        print("No updates needed for existing rows.")

    if rows_to_add:
        print(f"Found {len(rows_to_add)} new rows to add. Adding...")
        smart.Sheets.add_rows(target_sheet_id, rows_to_add)
        print("Successfully added new rows.")
    else:
        print("No new rows to add.")

# --- MAIN DISPATCHER ---

def main_process(smart, config):
    """Main function to dispatch tasks based on sync_mode."""
    source_sheet_id = config['source_sheet_id']
    print("--- Starting Sync Process ---")
    
    try:
        source_sheet = smart.Sheets.get_sheet(source_sheet_id)
        print(f"Successfully loaded source sheet: '{source_sheet.name}' with {len(source_sheet.rows)} rows.")
    except Exception as e:
        print(f"FATAL ERROR: Could not load source sheet. Halting. Error: {e}")
        return

    for target_config in config['targets']:
        sync_mode = target_config.get('sync_mode', 'update') # Default to 'update' if not specified
        print(f"\nProcessing target: '{target_config['description']}' (ID: {target_config['id']}) with '{sync_mode}' mode.")
        
        try:
            if sync_mode == 'snapshot':
                handle_snapshot_sync(smart, source_sheet, target_config)
            elif sync_mode == 'update':
                handle_update_sync(smart, source_sheet, target_config)
            else:
                print(f"WARNING: Unknown sync_mode '{sync_mode}'. Skipping target.")
        except Exception as e:
            print(f"ERROR processing target {target_config['id']}. Error: {e}")

    print("\n--- Sync Process Complete ---")

if __name__ == '__main__':
    access_token = os.getenv('SMARTSHEET_ACCESS_TOKEN')
    if not access_token:
        raise ValueError("FATAL ERROR: SMARTSHEET_ACCESS_TOKEN environment variable not found.")

    smartsheet_client = smartsheet.Smartsheet(access_token)
    smartsheet_client.errors_as_exceptions(True)
    main_process(smartsheet_client, SHEET_CONFIG)
