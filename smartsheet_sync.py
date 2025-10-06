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

def resolve_column_id(column_ref, column_map):
    """
    Accepts either a numeric column ID or a column title string and returns the numeric ID.
    If a string is provided and not found in the map, returns None.
    """
    if isinstance(column_ref, int):
        return column_ref
    if isinstance(column_ref, str):
        return column_map.get(column_ref)
    return None

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

    # Resolve tracking and generated columns (support name or ID in config)
    tracking_col_id = resolve_column_id(target_config['tracking_column_name'], target_col_map)
    generated_cols_config = target_config.get('generated_columns', {})
    week_end_col_id = resolve_column_id(generated_cols_config.get('week_ending_date'), target_col_map)
    week_num_col_id = resolve_column_id(generated_cols_config.get('week_number'), target_col_map)

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
        sync_end_date_str = target_config.get('sync_end_date')
        sync_start_date = None
        sync_end_date = None
        if sync_start_date_str:
            sync_start_date = datetime.strptime(sync_start_date_str, '%Y-%m-%d').date()
            print(f"Backfill will respect date filter: only processing dates from {sync_start_date_str} onwards")
        if sync_end_date_str:
            sync_end_date = datetime.strptime(sync_end_date_str, '%Y-%m-%d').date()
            print(f"Backfill will respect end date filter: only processing dates up to {sync_end_date_str}")
        
        for item in rows_needing_backfill:
            try:
                historical_wed = datetime.strptime(item['week_ending_date_str'], '%Y-%m-%d').date()
                
                # Skip backfill if this date is before the sync start date
                if sync_start_date and historical_wed < sync_start_date:
                    print(f"  - Skipping backfill for {item['week_ending_date_str']} (before sync start date)")
                    continue
                # Skip backfill if this date is after the sync end date
                if sync_end_date and historical_wed > sync_end_date:
                    print(f"  - Skipping backfill for {item['week_ending_date_str']} (after sync end date)")
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
    sync_end_date_str = target_config.get('sync_end_date')
    weeks_to_process = [current_wed]  # Always process current week
    
    if sync_start_date_str:
        sync_start_date = datetime.strptime(sync_start_date_str, '%Y-%m-%d').date()
        if current_wed < sync_start_date:
            print(f"Current week ending date ({current_wed_str}) is before sync start date ({sync_start_date_str}). Skipping sync for this target.")
            return
        
        if sync_end_date_str:
            sync_end_date = datetime.strptime(sync_end_date_str, '%Y-%m-%d').date()
            if current_wed > sync_end_date:
                print(f"Current week ending date ({current_wed_str}) is after sync end date ({sync_end_date_str}). Skipping sync for this target.")
                return
            print(f"Date filter active: Syncing data from {sync_start_date_str} to {sync_end_date_str}. Current week ending: {current_wed_str}")
        else:
            print(f"Date filter active: Only syncing data from {sync_start_date_str} onwards. Current week ending: {current_wed_str}")
        
        # Generate all missing weeks from sync start date to current week
        # Find the first Sunday on or after the sync start date
        first_sunday = sync_start_date
        days_until_sunday = (6 - first_sunday.weekday() + 7) % 7
        if days_until_sunday > 0:
            first_sunday = first_sunday + timedelta(days=days_until_sunday)
        
        # Generate all Sundays (week ending dates) from first_sunday to current_wed
        missing_weeks = []
        week_date = first_sunday
        # If there's an end date, limit generation up to that end date (inclusive for processing logic)
        if sync_end_date_str:
            sync_end_date = datetime.strptime(sync_end_date_str, '%Y-%m-%d').date()
        else:
            sync_end_date = None

        while week_date < current_wed and (sync_end_date is None or week_date <= sync_end_date):
            week_date_str = week_date.strftime('%Y-%m-%d')
            # Check if this week already has snapshots for all source rows
            has_complete_snapshot = True
            for source_row in source_sheet.rows:
                composite_key = (source_row.id, week_date_str)
                if composite_key not in target_snapshot_map:
                    has_complete_snapshot = False
                    break
            
            if not has_complete_snapshot:
                missing_weeks.append(week_date)
            
            week_date += timedelta(days=7)
        
        if missing_weeks:
            print(f"Found {len(missing_weeks)} missing weeks to backfill: {[w.strftime('%Y-%m-%d') for w in missing_weeks]}")
            weeks_to_process = missing_weeks + [current_wed]
        else:
            print("No missing weeks found - all historical data is present")

    print(f"Processing {len(weeks_to_process)} week(s): {[w.strftime('%Y-%m-%d') for w in weeks_to_process]}")
    print(f"Found {len(target_snapshot_map)} existing snapshot entries in target.")

    all_rows_to_add = []
    all_rows_to_update = []

    for week_ending_date in weeks_to_process:
        week_ending_str = week_ending_date.strftime('%Y-%m-%d')
        week_num = calculate_week_number(week_ending_date)
        
        print(f"\n--- Processing Week Ending: {week_ending_str} (Project Week: {week_num}) ---")
        
        rows_to_add = []
        rows_to_update = []

        for source_row in source_sheet.rows:
            composite_key = (source_row.id, week_ending_str)
            
            if composite_key in target_snapshot_map:
                # --- UPDATE LOGIC (only for current week) ---
                if week_ending_date == current_wed:
                    target_row = target_snapshot_map[composite_key]
                    update_row = smartsheet.models.Row({'id': target_row.id, 'cells': []})
                    needs_update = False
                    
                    for source_col_id, target_col_ref in target_config['column_id_mapping'].items():
                        target_col_id = resolve_column_id(target_col_ref, target_col_map)
                        if target_col_id is None:
                            print(f"    ! Skipping mapping for target column ref '{target_col_ref}' (not found)")
                            continue
                        source_cell = source_row.get_column(source_col_id)
                        target_cell = target_row.get_column(target_col_id)
                        
                        source_value = source_cell.value if source_cell else None
                        target_value = target_cell.value if target_cell else None

                        if source_value != target_value:
                            print(f"  - Updating snapshot for source row {source_row.id}. Value for target column {target_col_id} changed from '{target_value}' to '{source_value}'.")
                            needs_update = True
                            update_row.cells.append(smartsheet.models.Cell({'column_id': target_col_id, 'value': source_value or ""}))
                    
                    if needs_update:
                        rows_to_update.append(update_row)
                # Historical weeks already exist, skip them
            else:
                # --- ADD LOGIC (for all missing weeks) ---
                print(f"  - Preparing new snapshot for source row ID: {source_row.id}")
                new_row = smartsheet.models.Row({'to_bottom': True, 'cells': []})
                
                for source_col_id, target_col_ref in target_config['column_id_mapping'].items():
                    target_col_id = resolve_column_id(target_col_ref, target_col_map)
                    if target_col_id is None:
                        print(f"    ! Skipping mapping for target column ref '{target_col_ref}' (not found)")
                        continue
                    source_cell = source_row.get_column(source_col_id)
                    source_value = source_cell.value if source_cell else ""
                    new_row.cells.append(smartsheet.models.Cell({'column_id': target_col_id, 'value': source_value}))
                
                new_row.cells.append(smartsheet.models.Cell({'column_id': tracking_col_id, 'value': source_row.id}))
                new_row.cells.append(smartsheet.models.Cell({'column_id': week_end_col_id, 'value': week_ending_str}))
                
                if week_num_col_id:
                    new_row.cells.append(smartsheet.models.Cell({'column_id': week_num_col_id, 'value': week_num}))
                
                rows_to_add.append(new_row)

        all_rows_to_add.extend(rows_to_add)
        all_rows_to_update.extend(rows_to_update)
        
        if rows_to_add:
            print(f"  - Will create {len(rows_to_add)} new snapshot rows for week {week_ending_str}")
        if rows_to_update:
            print(f"  - Will update {len(rows_to_update)} existing snapshot rows for week {week_ending_str}")

    # --- BATCH OPERATIONS ---
    if all_rows_to_update:
        print(f"\nUpdating {len(all_rows_to_update)} existing snapshot rows with current data...")
        smart.Sheets.update_rows(target_sheet_id, all_rows_to_update)
        print("Successfully updated rows.")

    if all_rows_to_add:
        print(f"\nCreating {len(all_rows_to_add)} new snapshot rows...")
        
        # Process in batches of 500 to avoid API limits and timeouts
        batch_size = 500
        total_batches = (len(all_rows_to_add) + batch_size - 1) // batch_size
        
        for i in range(0, len(all_rows_to_add), batch_size):
            batch = all_rows_to_add[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            print(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} rows)...")
            smart.Sheets.add_rows(target_sheet_id, batch)
            print(f"  Batch {batch_num} completed successfully.")
        
        print("Successfully created all snapshot rows.")
    else:
        print("\nNo new snapshot rows to create.")

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
