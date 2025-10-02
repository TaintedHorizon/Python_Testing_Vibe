# 🤖 AI Assistant Quick Reference

## ⚠️ CRITICAL COMMANDS (Use These!)

### **Start Application**
```bash
cd /home/svc-scan/Python_Testing_Vibe && ./start_app.sh
```

### **Activate Virtual Environment**
```bash
cd /home/svc-scan/Python_Testing_Vibe/doc_processor
source venv/bin/activate
```

### **Configuration Import**
```python
from config_manager import app_config
```

### **Database Connection**
```python
from database import database_connection
with database_connection() as conn:
    cursor = conn.cursor()
```

## 🚨 NEVER DO THESE
- ❌ `python app.py`
- ❌ `source .venv/bin/activate`
- ❌ `from config import SETTING`
- ❌ `source doc_processor_env/bin/activate`

## 📖 Full Instructions
See `.github/copilot-instructions.md` for complete details.