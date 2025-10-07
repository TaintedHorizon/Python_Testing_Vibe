<!-- Moved from repository root to doc_processor/docs for consolidation -->
# 🤖 AI Assistant Quick Reference

This quick reference was relocated from the repo root to keep all processor‑specific documentation under `doc_processor/docs/`.

For complete operational guardrails see: `.github/copilot-instructions.md`.

## ⚠️ Critical Commands
```bash
cd /home/svc-scan/Python_Testing_Vibe && ./start_app.sh
cd /home/svc-scan/Python_Testing_Vibe/doc_processor && source venv/bin/activate
```

## Imports
```python
from config_manager import app_config
from database import database_connection
```

## Never Do
- python app.py
- source .venv/bin/activate (wrong path)
- from config import ... (use config_manager)

See `ARCHITECTURE.md` for full file map.