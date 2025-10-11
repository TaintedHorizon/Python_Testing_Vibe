import os
import sys
import argparse
from dotenv import load_dotenv

# Load environment variables (for DATABASE_PATH)
load_dotenv()

parser = argparse.ArgumentParser(description='Force reset a batch to start (destructive)')
parser.add_argument('--batch', type=int, default=1, help='Batch ID to reset')
parser.add_argument('--dry-run', action='store_true', help='Show what would be done without applying changes')
parser.add_argument('--yes', '-y', action='store_true', help='Auto-confirm destructive action (or set CONFIRM_RESET=1)')
args = parser.parse_args()

dry_run = args.dry_run or os.getenv('DRY_RUN','0').lower() in ('1','true','t')
env_confirm = os.getenv('CONFIRM_RESET','0').lower() in ('1','true','t')
if not (env_confirm or args.yes):
	confirm = input(f"This will reset batch {args.batch} to start and may delete data. Type 'yes' to continue: ")
	if confirm.lower() != 'yes':
		print("Operation cancelled (no confirmation).")
		sys.exit(0)

if dry_run:
	print(f"DRY-RUN: would reset batch {args.batch} to start (no changes applied)")
else:
	from doc_processor.database import reset_batch_to_start
	reset_batch_to_start(args.batch)
	print(f"Batch {args.batch} has been fully reset.")
