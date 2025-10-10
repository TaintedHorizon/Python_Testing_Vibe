"""
Small script to test production-style Ollama call with OLLAMA_NUM_GPU=0.
It forces OLLAMA_NUM_GPU=0, unsets FAST_TEST_MODE, inspects CUDA_VISIBLE_DEVICES
and torch.cuda availability, then calls doc_processor.llm_utils._query_ollama.

Run with the project venv Python to match runtime environment.
"""
import os
import sys
import traceback
import pytest

# This is an interactive/dev script intended to be run manually. Prevent
# pytest from importing and executing it during automated collection.
pytest.skip("Dev-only production Ollama probe - skip during automated test runs", allow_module_level=True)

# Force production-style env: GPU count 0 and ensure tests mode is off
os.environ['OLLAMA_NUM_GPU'] = '0'
if 'FAST_TEST_MODE' in os.environ:
    del os.environ['FAST_TEST_MODE']

print("ENV before prepare: CUDA_VISIBLE_DEVICES=", os.environ.get('CUDA_VISIBLE_DEVICES'))

# Import helpers from the project
try:
    from doc_processor.llm_utils import _ollama_use_gpu, _prepare_ollama_env_for_use, _query_ollama
except Exception as e:
    print("Failed to import llm_utils:", e)
    traceback.print_exc()
    sys.exit(2)

# Check torch GPU availability if present
try:
    import torch
    try:
        print("torch.cuda.is_available() before prepare:", torch.cuda.is_available())
    except Exception as te:
        print("torch import ok but cuda check failed:", te)
except Exception as ie:
    print("torch not importable:", ie)

# Apply environment preparation for Ollama (should clear CUDA_VISIBLE_DEVICES when GPU disabled)
try:
    _prepare_ollama_env_for_use()
    print("ENV after prepare: CUDA_VISIBLE_DEVICES=", os.environ.get('CUDA_VISIBLE_DEVICES'))
    print("_ollama_use_gpu() ->", _ollama_use_gpu())
except Exception as e:
    print("_prepare_ollama_env_for_use failed:", e)
    traceback.print_exc()

# Try importing ollama module
try:
    import ollama
    print("ollama module importable: OK (version/obj)", getattr(ollama, '__version__', repr(ollama)))
except Exception as ie:
    print("ollama import failed:", ie)

# Attempt to call the centralized _query_ollama
try:
    print("Calling _query_ollama with a short prompt (timeout=15s)...")
    result = _query_ollama("Please respond with 'CPU' or 'GPU' to indicate where you ran.", timeout=15, task_name='prod_test')
    print("_query_ollama result:", repr(result))
except Exception as e:
    print("_query_ollama call raised exception:", e)
    traceback.print_exc()

print("Done.")
