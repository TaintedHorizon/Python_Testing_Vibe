# Filing Cabinet Naming Cleanup Tool

## Overview
This utility standardizes all directory and file names in your filing cabinet to match the new consistent naming convention used by both single document and batch export workflows.

## Features
- **Preview Mode**: See exactly what changes will be made before applying them
- **Automatic Backup**: Creates a complete backup before making any changes
- **Rollback Capability**: Can completely undo all changes if needed
- **Conflict Resolution**: Handles duplicate names by adding numeric suffixes
- **Detailed Logging**: Comprehensive logs of all operations

## Naming Conventions Applied
- **Directory Names**: Spaces → underscores (e.g., "Medical Records" → "Medical_Records")
- **File Names**: Non-alphanumeric characters → underscores, except dots and hyphens (e.g., "Julian's Invoice.pdf" → "Julian_s_Invoice.pdf")

## Usage

### 1. Preview Changes (Recommended First Step)
```bash
cd /home/svc-scan/Python_Testing_Vibe
source doc_processor/venv/bin/activate
python doc_processor/dev_tools/cleanup_filing_cabinet_names.py --dry-run
```

### 2. Apply Changes
```bash
python doc_processor/dev_tools/cleanup_filing_cabinet_names.py --apply
```

### 3. Rollback Changes (if needed)
```bash
python doc_processor/dev_tools/cleanup_filing_cabinet_names.py --rollback
```

### 4. Override Filing Cabinet Directory
```bash
python doc_processor/dev_tools/cleanup_filing_cabinet_names.py --dry-run --filing-cabinet /path/to/custom/directory
```

## Safety Features

### Automatic Backup
- Creates `.cleanup_backup` directory with complete copy of filing cabinet
- Backup is created before any changes are made
- Only removed when you explicitly delete it

### Conflict Resolution
If multiple files would have the same name after sanitization:
- First file keeps the sanitized name
- Subsequent files get numeric suffixes (_1, _2, etc.)
- Example: "Contract.pdf" and "Contract!.pdf" → "Contract.pdf" and "Contract_1.pdf"

### Comprehensive Logging
- Console output shows progress
- Detailed log saved to `cleanup.log` in filing cabinet
- Change history saved to `cleanup_log.json` for rollback operations

## Example Output

```
Scanning filing cabinet...
Scan Results:
  Total directories: 15
  Total files: 276
  Directories needing rename: 8
  Files needing rename: 3

Directory: Form or Application → Form_or_Application
Directory: Medical Record → Medical_Record
File: Julian's Invoice.pdf → Julian_s_Invoice.pdf

=== 11 operations would be performed ===
```

## Troubleshooting

### Import Errors
Make sure you're running from the project root with the virtual environment activated:
```bash
cd /home/svc-scan/Python_Testing_Vibe
source doc_processor/venv/bin/activate
```

### Permission Errors
Ensure you have write permissions to the filing cabinet directory.

### Rollback Issues
If rollback fails, the backup is still available in `.cleanup_backup` and can be manually restored.

## Best Practices

1. **Always run --dry-run first** to see what changes will be made
2. **Check the preview output carefully** before applying changes
3. **Keep the backup** until you're sure everything works correctly
4. **Test a small subset first** if you have a large filing cabinet (use --filing-cabinet to specify a subdirectory)

## File Structure After Cleanup

Your filing cabinet will have:
- Standardized directory names with underscores
- Standardized file names with underscores for special characters
- `.cleanup_backup/` directory (can be deleted when you're satisfied)
- `cleanup.log` and `cleanup_log.json` (operation logs)

This ensures consistency with the new export workflows and better filesystem compatibility.