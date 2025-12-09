# smartsheet_sync.py

import os
import smartsheet
from config import SHEET_CONFIG
from datetime import datetime, date, timedelta

# ============================================================================
# CONFIGURATION FLAGS
# ============================================================================
# Enable historical backfill to create missing snapshot rows for past weeks
# Set to True for initial run to fill gaps, then can be set to False
ENABLE_HISTORICAL_BACKFILL = True

# Start date for historical backfill - scans all weeks from this date forward
HISTORICAL_BACKFILL_START = '2025-06-15'

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

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

def normalize_tracking_id(tracking_value):
    """
    Normalizes tracking ID to ensure consistent string comparison.
    Converts integers to strings for composite key matching.
    """
    if tracking_value is None:
        return None
    return str(tracking_value)

def generate_composite_tracking_id(source_sheet_id, row_id):
    """
    Generates a composite tracking ID for multi-source scenarios.
    Format: {source_sheet_id}_{row_id}
    """
    return f"{source_sheet_id}_{row_id}"

def load_all_source_data(smart, source_sheets_config):
    """
    Loads data from all configured source sheets.
    Returns a list of tuples: (source_sheet_object, source_config)
    """
    source_data = []
    for source_config in source_sheets_config:
        source_sheet_id = source_config['id']
        try:
            source_sheet = smart.Sheets.get_sheet(source_sheet_id)
            print(f"  Loaded source sheet '{source_sheet.name}' (ID: {source_sheet_id}) with {len(source_sheet.rows)} rows")
            source_data.append((source_sheet, source_config))
        except Exception as e:
            print(f"  ERROR: Could not load source sheet {source_sheet_id}: {e}")
    return source_data

def get_all_source_rows(source_data_list):
    """
    Collects all source rows from multiple source sheets with proper tracking IDs.
    Returns a list of tuples: (source_row, composite_tracking_id, source_config)
    """
    all_rows = []
    for source_sheet, source_config in source_data_list:
        source_sheet_id = source_config['id']
        for row in source_sheet.rows:
            composite_id = generate_composite_tracking_id(source_sheet_id, row.id)
            all_rows.append((row, composite_id, source_config))
    return all_rows

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
    1. A map of (normalized_source_id, date) -> target_row_object for update/enrichment checks.
    2. A list of rows that need their week number backfilled.
    3. A set of unique week ending dates already present in the sheet.
    """
    snapshot_map = {}
    rows_to_backfill = []
    existing_week_dates = set()
    
    # We need all columns to check for blank cells, so we fetch the full sheet data here.
    for row in smart.Sheets.get_sheet(sheet.id, include=['data']).rows:
        tracking_cell = row.get_column(tracking_col_id)
        week_end_cell = row.get_column(week_end_col_id)
        week_num_cell = row.get_column(week_num_col_id) if week_num_col_id else None

        if tracking_cell and tracking_cell.value and week_end_cell and week_end_cell.value:
            # Normalize tracking ID to string for consistent comparison
            normalized_tracking_id = normalize_tracking_id(tracking_cell.value)
            composite_key = (normalized_tracking_id, week_end_cell.value)
            snapshot_map[composite_key] = row # Store the full row object
            existing_week_dates.add(week_end_cell.value)

            if week_num_col_id and (week_num_cell is None or week_num_cell.value is None):
                rows_to_backfill.append({
                    'target_row_id': row.id,
                    'week_ending_date_str': week_end_cell.value
                })
    return snapshot_map, rows_to_backfill, existing_week_dates

# --- LOGIC HANDLERS ---

def handle_snapshot_sync(smart, source_data_list, target_config):
    """
    Handles snapshot synchronization for a target sheet.
    Supports multiple source sheets and historical backfill.
    
    Args:
        smart: Smartsheet client
        source_data_list: List of tuples (source_sheet, source_config)
        target_config: Target sheet configuration
    """
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
    target_snapshot_map, rows_needing_backfill, existing_week_dates = get_snapshot_metadata(
        smart, target_sheet, tracking_col_id, week_end_col_id, week_num_col_id
    )
    
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

    # Get all source rows with composite tracking IDs
    all_source_rows = get_all_source_rows(source_data_list)
    total_source_rows = len(all_source_rows)
    print(f"Total source rows across all source sheets: {total_source_rows}")

    # Check if this target has a sync start date filter
    sync_start_date_str = target_config.get('sync_start_date')
    sync_end_date_str = target_config.get('sync_end_date')
    weeks_to_process = [current_wed]  # Always process current week
    
    # Determine the earliest start date for historical backfill
    if ENABLE_HISTORICAL_BACKFILL and sync_start_date_str:
        backfill_start = datetime.strptime(HISTORICAL_BACKFILL_START, '%Y-%m-%d').date()
        sync_start_date = datetime.strptime(sync_start_date_str, '%Y-%m-%d').date()
        
        # Use the later of the two dates (backfill start or sync start)
        effective_start_date = max(backfill_start, sync_start_date)
        
        if current_wed < effective_start_date:
            print(f"Current week ending date ({current_wed_str}) is before effective start date ({effective_start_date}). Skipping sync for this target.")
            return
        
        if sync_end_date_str:
            sync_end_date = datetime.strptime(sync_end_date_str, '%Y-%m-%d').date()
            if current_wed > sync_end_date:
                print(f"Current week ending date ({current_wed_str}) is after sync end date ({sync_end_date_str}). Skipping sync for this target.")
                return
            print(f"Date filter active: Syncing data from {effective_start_date} to {sync_end_date_str}. Current week ending: {current_wed_str}")
        else:
            sync_end_date = None
            print(f"Date filter active: Only syncing data from {effective_start_date} onwards. Current week ending: {current_wed_str}")
        
        # Generate all missing weeks from effective start date to current week
        # Find the first Sunday on or after the effective start date
        first_sunday = effective_start_date
        days_until_sunday = (6 - first_sunday.weekday() + 7) % 7
        if days_until_sunday > 0:
            first_sunday = first_sunday + timedelta(days=days_until_sunday)
        
        # Generate all Sundays (week ending dates) from first_sunday to current_wed
        missing_weeks = []
        week_date = first_sunday

        while week_date < current_wed and (sync_end_date is None or week_date <= sync_end_date):
            week_date_str = week_date.strftime('%Y-%m-%d')
            
            # Count how many rows exist for this week
            existing_count = sum(1 for source_row, composite_id, _ in all_source_rows 
                               if (normalize_tracking_id(composite_id), week_date_str) in target_snapshot_map)
            
            # Check if this week has incomplete snapshot
            if existing_count < total_source_rows:
                print(f"  Week {week_date_str}: {existing_count}/{total_source_rows} rows exist - marking for backfill")
                missing_weeks.append(week_date)
            else:
                print(f"  Week {week_date_str}: Complete ({existing_count}/{total_source_rows} rows)")
            
            week_date += timedelta(days=7)
        
        if missing_weeks:
            print(f"\nFound {len(missing_weeks)} weeks with incomplete snapshots to backfill")
            weeks_to_process = missing_weeks + [current_wed]
        else:
            print("\nNo missing weeks found - all historical data is complete")
    elif sync_start_date_str:
        # No historical backfill, just respect sync dates
        sync_start_date = datetime.strptime(sync_start_date_str, '%Y-%m-%d').date()
        if current_wed < sync_start_date:
            print(f"Current week ending date ({current_wed_str}) is before sync start date ({sync_start_date_str}). Skipping sync for this target.")
            return
        
        if sync_end_date_str:
            sync_end_date = datetime.strptime(sync_end_date_str, '%Y-%m-%d').date()
            if current_wed > sync_end_date:
                print(f"Current week ending date ({current_wed_str}) is after sync end date ({sync_end_date_str}). Skipping sync for this target.")
                return

    print(f"\nProcessing {len(weeks_to_process)} week(s): {[w.strftime('%Y-%m-%d') for w in weeks_to_process]}")
    print(f"Found {len(target_snapshot_map)} existing snapshot entries in target.")

    all_rows_to_add = []
    all_rows_to_update = []

    for week_ending_date in weeks_to_process:
        week_ending_str = week_ending_date.strftime('%Y-%m-%d')
        week_num = calculate_week_number(week_ending_date)
        
        print(f"\n--- Processing Week Ending: {week_ending_str} (Project Week: {week_num}) ---")
        
        rows_to_add = []
        rows_to_update = []

        for source_row, composite_tracking_id, source_config in all_source_rows:
            normalized_tracking_id = normalize_tracking_id(composite_tracking_id)
            composite_key = (normalized_tracking_id, week_ending_str)
            
            if composite_key in target_snapshot_map:
                # --- UPDATE LOGIC (only for current week) ---
                if week_ending_date == current_wed:
                    target_row = target_snapshot_map[composite_key]
                    update_row = smartsheet.models.Row({'id': target_row.id, 'cells': []})
                    needs_update = False
                    
                    # Get the work request column from source
                    source_work_request_col_id = source_config['work_request_column_id']
                    
                    # Get target work request column
                    target_work_request_col = target_config.get('target_work_request_column')
                    if target_work_request_col is None:
                        # Fall back to first mapping in column_id_mapping
                        for src_col, tgt_col in target_config['column_id_mapping'].items():
                            target_work_request_col = resolve_column_id(tgt_col, target_col_map)
                            break
                    
                    if target_work_request_col:
                        source_cell = source_row.get_column(source_work_request_col_id)
                        target_cell = target_row.get_column(target_work_request_col)
                        
                        source_value = source_cell.value if source_cell else None
                        target_value = target_cell.value if target_cell else None

                        if source_value != target_value:
                            update_value = source_value if source_value is not None else ""
                            print(f"  - Updating snapshot for tracking ID {composite_tracking_id}. Value changed from '{target_value}' to '{source_value}'.")
                            needs_update = True
                            update_row.cells.append(smartsheet.models.Cell({'column_id': target_work_request_col, 'value': update_value}))
                    
                    if needs_update:
                        rows_to_update.append(update_row)
                # Historical weeks already exist, skip them
            else:
                # --- ADD LOGIC (for all missing weeks) ---
                print(f"  - Preparing new snapshot for tracking ID: {composite_tracking_id}")
                new_row = smartsheet.models.Row({'to_bottom': True, 'cells': []})
                
                # Get the work request column from source
                source_work_request_col_id = source_config['work_request_column_id']
                source_cell = source_row.get_column(source_work_request_col_id)
                source_value = source_cell.value if source_cell else None
                
                # Get target work request column
                target_work_request_col = target_config.get('target_work_request_column')
                if target_work_request_col is None:
                    # Fall back to first mapping in column_id_mapping
                    for src_col, tgt_col in target_config['column_id_mapping'].items():
                        target_work_request_col = resolve_column_id(tgt_col, target_col_map)
                        break
                
                if target_work_request_col:
                    # Ensure we always have a valid value (convert None to empty string)
                    if source_value is None:
                        source_value = ""
                    new_row.cells.append(smartsheet.models.Cell({'column_id': target_work_request_col, 'value': source_value}))
                
                new_row.cells.append(smartsheet.models.Cell({'column_id': tracking_col_id, 'value': composite_tracking_id}))
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
    print("--- Starting Sync Process ---")
    
    # Check if we have multi-source configuration
    source_sheets_config = config.get('source_sheets')
    legacy_source_sheet_id = config.get('source_sheet_id')
    
    # Load source data
    source_data_list = []
    if source_sheets_config:
        print(f"Loading {len(source_sheets_config)} source sheets...")
        source_data_list = load_all_source_data(smart, source_sheets_config)
        if not source_data_list:
            print("FATAL ERROR: Could not load any source sheets. Halting.")
            return
    elif legacy_source_sheet_id:
        # Legacy single source mode for update targets
        try:
            source_sheet = smart.Sheets.get_sheet(legacy_source_sheet_id)
            print(f"Successfully loaded legacy source sheet: '{source_sheet.name}' with {len(source_sheet.rows)} rows.")
            # Create a dummy config for legacy mode
            legacy_config = {
                'id': legacy_source_sheet_id,
                'description': 'Legacy Source Sheet',
                'work_request_column_id': None  # Not used in legacy update mode
            }
            source_data_list = [(source_sheet, legacy_config)]
        except Exception as e:
            print(f"FATAL ERROR: Could not load source sheet. Halting. Error: {e}")
            return
    else:
        print("FATAL ERROR: No source sheet configuration found. Halting.")
        return

    for target_config in config['targets']:
        sync_mode = target_config.get('sync_mode', 'update')
        print(f"\n{'='*80}")
        print(f"Processing target: '{target_config['description']}' (ID: {target_config['id']})")
        print(f"Sync mode: '{sync_mode}'")
        print(f"{'='*80}")
        
        try:
            if sync_mode == 'snapshot':
                handle_snapshot_sync(smart, source_data_list, target_config)
            elif sync_mode == 'update':
                # Update mode still uses single source (first source or legacy)
                source_sheet = source_data_list[0][0] if source_data_list else None
                if source_sheet:
                    handle_update_sync(smart, source_sheet, target_config)
                else:
                    print(f"WARNING: No source sheet available for update mode. Skipping target.")
            else:
                print(f"WARNING: Unknown sync_mode '{sync_mode}'. Skipping target.")
        except Exception as e:
            print(f"ERROR processing target {target_config['id']}. Error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*80)
    print("--- Sync Process Complete ---")
    print("="*80)

if __name__ == '__main__':
    access_token = os.getenv('SMARTSHEET_ACCESS_TOKEN')
    if not access_token:
        raise ValueError("FATAL ERROR: SMARTSHEET_ACCESS_TOKEN environment variable not found.")

    smartsheet_client = smartsheet.Smartsheet(access_token)
    smartsheet_client.errors_as_exceptions(True)
    main_process(smartsheet_client, SHEET_CONFIG)
