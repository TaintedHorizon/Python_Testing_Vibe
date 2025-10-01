# Flask App Refactoring Plan

## 🚨 Current Problem
- **app.py is 2947 lines** with 68 functions and 60 routes
- Too large to edit safely - prone to indentation/syntax errors
- Difficult to maintain, debug, and understand
- Single point of failure for entire application

## 🎯 Proposed Solution: Modular Architecture

### 1. **Core Application Structure**
```
doc_processor/
├── app.py (main app factory - ~100 lines)
├── routes/
│   ├── __init__.py
│   ├── intake.py          # Intake analysis routes
│   ├── batch.py           # Batch control and management  
│   ├── manipulation.py    # Document manipulation
│   ├── export.py          # Export and finalization
│   ├── admin.py           # Admin and category management
│   └── api.py             # API endpoints and SSE
├── services/
│   ├── __init__.py
│   ├── batch_service.py   # Batch business logic
│   ├── document_service.py # Document operations
│   ├── category_service.py # Category management
│   └── export_service.py  # Export operations
├── utils/
│   ├── __init__.py
│   ├── helpers.py         # Utility functions
│   └── decorators.py      # Custom decorators
└── (existing files...)
```

### 2. **Benefits of Refactoring**
- ✅ **Smaller files** - easier to edit without errors
- ✅ **Clear separation** - each file has single responsibility  
- ✅ **Reduced conflicts** - multiple people can work on different areas
- ✅ **Better testing** - easier to unit test individual components
- ✅ **Improved maintainability** - find and fix issues faster
- ✅ **Future-proof** - easier to add new features

### 3. **Migration Strategy**
1. **Phase 1**: Extract route groups into blueprints
2. **Phase 2**: Move business logic to service classes  
3. **Phase 3**: Extract utility functions
4. **Phase 4**: Create proper application factory pattern

### 4. **File Size Targets**
- Main `app.py`: ~100 lines (app factory + config)
- Route files: ~200-400 lines each
- Service files: ~300-500 lines each
- No single file over 600 lines

### 5. **Immediate Actions**
1. Create route blueprints for major sections
2. Extract helper functions to utils
3. Move database operations to services
4. Update imports and test functionality

## 🚀 Implementation Priority
1. **High Priority**: Intake, Batch, Export routes (most used)
2. **Medium Priority**: Manipulation, Admin routes  
3. **Low Priority**: API endpoints (working well currently)

This refactoring will solve the editing problems and make the codebase much more maintainable!