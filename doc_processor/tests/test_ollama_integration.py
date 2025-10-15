import os
import pytest

pytestmark = pytest.mark.skipif(os.getenv('RUN_OLLAMA_INTEGRATION') != '1', reason='Integration tests disabled')

def test_ollama_cpu_hint():
    """Integration test: verify Ollama returns CPU when num_gpu=0 is requested.

    This test is skipped by default. Enable by setting RUN_OLLAMA_INTEGRATION=1
    and ensuring OLLAMA_HOST and model are reachable.
    """
    from config_manager import app_config
    from ollama import Client

    os.environ.setdefault('OLLAMA_NUM_GPU', '0')
    client = Client(host=app_config.OLLAMA_HOST)
    options = {'num_ctx': 256, 'num_gpu': 0}
    prompt = 'Please reply with the single word CPU or GPU that indicates which device you executed on.'
    resp = client.chat(model=app_config.OLLAMA_MODEL, messages=[{'role':'user','content':prompt}], options=options)
    # Extract content
    msg = getattr(resp, 'message', None)
    content = getattr(msg, 'content', '') if msg else str(resp)
    assert 'CPU' in content.upper() or 'GPU' in content.upper()
    assert 'CPU' in content.upper(), f"Expected CPU in reply, got: {content}"
