# smartsheet_sync.py

import os
import smartsheet
from config import SHEET_CONFIG
from datetime import datetime, date, timedelta

# --- HELPER FUNCTIONS ---

def get_current_week_ending_date():
    today = date.today()
    days_until_sunday = (6 - today.weekday() + 7) % 7
    return today + timedelta(days=days_until_sunday)

def calculate_week_number(current_wed, start_date_str='2025-06-15'):
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    return (current_wed - start_date).days // 7

def get_column_map_by_name(sheet):
    return {column.title: column.id for column in sheet.columns}

def get_target_row_map_for_update(smart, sheet, tracking_column_id):
    target_map = {}
    for row in sheet.rows:
        tracking_cell = row.get_column(tracking_column_id)
        if tracking_cell and tracking_cell.value:
            target_map[tracking_cell.value] = row
    return target_map

def get_snapshot_metadata(smart, sheet, tracking_col_id, week_end_col_id, week_num_col_id):
    """
    Scans a snapshot sheet to gather metadata.
    Returns:
    1. A map of (source_id, date) -> target_row_object for update/enrichment checks.
    2. A list of rows that need their week number backfilled.
    """
    snapshot_map = {}
    rows_to_backfill = []
    
    # We need all columns to check for blank cells, so we fetch the full sheet data here.
    for row in smart.Sheets.get_sheet(sheet.id, include=['data']).rows:
        tracking_cell = row.get_column(tracking_col_id)
        week_end_cell = row.get_column(week_end_col_id)
        week_num_cell = row.get_column(week_num_col_id) if week_num_col_id else None

        if tracking_cell and tracking_cell.value and week_end_cell and week_end_cell.value:
            composite_key = (tracking_cell.value, week_end_cell.value)
            snapshot_map[composite_key] = row # Store the full row object

            if week_num_col_id and (week_num_cell is None or week_num_cell.value is None):
                rows_to_backfill.append({
                    'target_row_id': row.id,
                    'week_ending_date_str': week_end_cell.value
                })
    return snapshot_map, rows_to_backfill

# --- LOGIC HANDLERS ---

def handle_snapshot_sync(smart, source_sheet, target_config):
    target_sheet_id = target_config['id']
    target_sheet = smart.Sheets.get_sheet(target_sheet_id)
    target_col_map = get_column_map_by_name(target_sheet)

    tracking_col_id = target_col_map[target_config['tracking_column_name']]
    
    generated_cols_config = target_config.get('generated_columns', {})
    week_end_col_id = generated_cols_config.get('week_ending_date')
    week_num_col_id = generated_cols_config.get('week_number')

    if not week_end_col_id:
        print("WARNING: 'week_ending_date' not configured for this snapshot sheet. Halting snapshot logic.")
        return

    # --- METADATA GATHERING ---
    target_snapshot_map, rows_needing_backfill = get_snapshot_metadata(smart, target_sheet, tracking_col_id, week_end_col_id, week_num_col_id)
    
    # --- BACKFILL LOGIC ---
    if rows_needing_backfill:
        print(f"Found {len(rows_needing_backfill)} existing rows missing a week number. Preparing to backfill...")
        rows_to_update_backfill = []
        
        # Get sync start date filter if configured
        sync_start_date_str = target_config.get('sync_start_date')
        sync_start_date = None
        if sync_start_date_str:
            sync_start_date = datetime.strptime(sync_start_date_str, '%Y-%m-%d').date()
            print(f"Backfill will respect date filter: only processing dates from {sync_start_date_str} onwards")
        
        for item in rows_needing_backfill:
            try:
                historical_wed = datetime.strptime(item['week_ending_date_str'], '%Y-%m-%d').date()
                
                # Skip backfill if this date is before the sync start date
                if sync_start_date and historical_wed < sync_start_date:
                    print(f"  - Skipping backfill for {item['week_ending_date_str']} (before sync start date)")
                    continue
                
                historical_week_num = calculate_week_number(historical_wed)
                update_row = smartsheet.models.Row({'id': item['target_row_id'], 'cells': [smartsheet.models.Cell({'column_id': week_num_col_id, 'value': historical_week_num})]})
                rows_to_update_backfill.append(update_row)
            except ValueError:
                print(f"  - WARNING: Could not parse date '{item['week_ending_date_str']}' for row ID {item['target_row_id']}. Skipping backfill for this row.")
        
        if rows_to_update_backfill:
            print(f"Backfilling week numbers for {len(rows_to_update_backfill)} rows...")
            smart.Sheets.update_rows(target_sheet_id, rows_to_update_backfill)
            print("Successfully backfilled week numbers.")

    # --- MAIN SNAPSHOT LOGIC (ADD or UPDATE) ---
    current_wed = get_current_week_ending_date()
    current_week_num = calculate_week_number(current_wed)
    current_wed_str = current_wed.strftime('%Y-%m-%d')

    # Check if this target has a sync start date filter
    sync_start_date_str = target_config.get('sync_start_date')
    if sync_start_date_str:
        sync_start_date = datetime.strptime(sync_start_date_str, '%Y-%m-%d').date()
        if current_wed < sync_start_date:
            print(f"Current week ending date ({current_wed_str}) is before sync start date ({sync_start_date_str}). Skipping sync for this target.")
            return
        print(f"Date filter active: Only syncing data from {sync_start_date_str} onwards. Current week ending: {current_wed_str}")

    print(f"Current Week Ending Date: {current_wed_str} (Project Week: {current_week_num})")
    print(f"Found {len(target_snapshot_map)} existing snapshot entries in target.")

    rows_to_add = []
    rows_to_update = [] 

    for source_row in source_sheet.rows:
        composite_key = (source_row.id, current_wed_str)
        
        if composite_key in target_snapshot_map:
            # --- RE-ENGINEERED: FULL UPDATE LOGIC ---
            # The snapshot for this week exists. Let's check if it needs an update.
            target_row = target_snapshot_map[composite_key]
            update_row = smartsheet.models.Row({'id': target_row.id, 'cells': []})
            needs_update = False
            
            for source_col_id, target_col_id in target_config['column_id_mapping'].items():
                source_cell = source_row.get_column(source_col_id)
                target_cell = target_row.get_column(target_col_id)
                
                source_value = source_cell.value if source_cell else None
                target_value = target_cell.value if target_cell else None

                # If the source value is different from the target value, we need to update.
                if source_value != target_value:
                    print(f"  - Updating snapshot for source row {source_row.id}. Value for target column {target_col_id} changed from '{target_value}' to '{source_value}'.")
                    needs_update = True
                    # Use source_value or "" to clear the cell if source is now blank
                    update_row.cells.append(smartsheet.models.Cell({'column_id': target_col_id, 'value': source_value or ""}))
            
            if needs_update:
                rows_to_update.append(update_row)

        else:
            # --- ADD LOGIC (Unchanged) ---
            # This is a new snapshot for this week.
            print(f"  - Preparing new snapshot for source row ID: {source_row.id}")
            new_row = smartsheet.models.Row({'to_bottom': True, 'cells': []})
            
            for source_col_id, target_col_id in target_config['column_id_mapping'].items():
                source_cell = source_row.get_column(source_col_id)
                source_value = source_cell.value if source_cell else ""
                print(f"    - Mapping Source Col {source_col_id} to Target Col {target_col_id}. Found value: '{source_value}'")
                new_row.cells.append(smartsheet.models.Cell({'column_id': target_col_id, 'value': source_value}))
            
            new_row.cells.append(smartsheet.models.Cell({'column_id': tracking_col_id, 'value': source_row.id}))
            new_row.cells.append(smartsheet.models.Cell({'column_id': week_end_col_id, 'value': current_wed_str}))
            
            if week_num_col_id:
                new_row.cells.append(smartsheet.models.Cell({'column_id': week_num_col_id, 'value': current_week_num}))
            
            rows_to_add.append(new_row)

    # --- BATCH OPERATIONS ---
    if rows_to_update:
        print(f"Updating {len(rows_to_update)} existing snapshot rows with current data...")
        smart.Sheets.update_rows(target_sheet_id, rows_to_update)
        print("Successfully updated rows.")

    if rows_to_add:
        print(f"Creating {len(rows_to_add)} new snapshot rows...")
        smart.Sheets.add_rows(target_sheet_id, rows_to_add)
        print("Successfully created snapshot rows.")
    else:
        print("No new snapshot rows to create for this week.")

def handle_update_sync(smart, source_sheet, target_config):
    # This function remains unchanged.
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
                new_row.cells.append(smartsheet.models.Cell({'column_id': tgt_id, 'value': (src_cell.value if src_cell else "") or ""}))
            new_row.cells.append(smartsheet.models.Cell({'column_id': tracking_col_id, 'value': source_row.id}))
            rows_to_add.append(new_row)

    if rows_to_update:
        print(f"Found {len(rows_to_update)} rows with changes. Updating...")
        smart.Sheets.update_rows(target_sheet_id, rows_to_update)
    else:
        print("No updates needed for existing rows.")

    if rows_to_add:
        print(f"Found {len(rows_to_add)} new rows to add. Adding...")
        smart.Sheets.add_rows(target_sheet_id, rows_to_add)
    else:
        print("No new rows to add.")

# --- MAIN DISPATCHER ---

def main_process(smart, config):
    source_sheet_id = config['source_sheet_id']
    print("--- Starting Sync Process ---")
    
    try:
        source_sheet = smart.Sheets.get_sheet(source_sheet_id)
        print(f"Successfully loaded source sheet: '{source_sheet.name}' with {len(source_sheet.rows)} rows.")
    except Exception as e:
        print(f"FATAL ERROR: Could not load source sheet. Halting. Error: {e}")
        return

    for target_config in config['targets']:
        sync_mode = target_config.get('sync_mode', 'update')
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
