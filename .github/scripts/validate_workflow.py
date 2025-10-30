#!/usr/bin/env python3
"""
Validate GitHub workflow YAML files for syntax errors.

This script loads YAML files using yaml.safe_load and checks for parsing errors.
Exits with non-zero status if any parse errors are detected.
"""
import sys
import yaml
import traceback


def validate_workflow(file_path):
    """
    Validate a single workflow YAML file.
    
    Args:
        file_path: Path to the YAML file to validate
        
    Returns:
        True if valid, False if invalid
    """
    try:
        with open(file_path, 'r') as fh:
            yaml.safe_load(fh)
        print(f"✓ {file_path}: Valid YAML")
        return True
    except yaml.YAMLError as e:
        print(f"✗ {file_path}: YAML parse error", file=sys.stderr)
        print(f"  Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return False
    except FileNotFoundError:
        print(f"✗ {file_path}: File not found", file=sys.stderr)
        return False
    except Exception as e:
        print(f"✗ {file_path}: Unexpected error", file=sys.stderr)
        print(f"  Error: {e}", file=sys.stderr)
        traceback.print_exc()
        return False


def main():
    """Main entry point for the validator script."""
    if len(sys.argv) < 2:
        print("Usage: validate_workflow.py <yaml_file> [<yaml_file> ...]", file=sys.stderr)
        sys.exit(1)
    
    files_to_validate = sys.argv[1:]
    all_valid = True
    
    for file_path in files_to_validate:
        if not validate_workflow(file_path):
            all_valid = False
    
    if not all_valid:
        print("\n❌ One or more workflow YAML files failed validation", file=sys.stderr)
        sys.exit(2)
    else:
        print("\n✅ All workflow YAML files validated successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
