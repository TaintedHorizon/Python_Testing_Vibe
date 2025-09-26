import logging
from typing import Optional
from .config_manager import app_config
def get_ai_document_type_analysis(file_path: str, content_sample: str, filename: str, page_count: int, file_size_mb: float) -> Optional[dict]:
    """
    Uses LLM to analyze document type based on content and metadata.
    Returns dict with classification, confidence, reasoning, and llm_used flag.
    """
    logging.info(f"🤖 get_ai_document_type_analysis called for {filename}")
    logging.debug(f"🤖 Parameters: pages={page_count}, size={file_size_mb}MB, content_len={len(content_sample)}")
    
    try:
        prompt = (
            f"""You are a document analysis expert. Analyze this document and determine if it should be processed as a SINGLE_DOCUMENT or BATCH_SCAN.\n\nFILE DETAILS:\n- Filename: {filename}\n- Page Count: {page_count}\n- File Size: {file_size_mb:.1f} MB\n\nDOCUMENT CONTENT SAMPLE:\n{content_sample[:2000]}\n\nANALYSIS TASK:\nClassify as SINGLE_DOCUMENT or BATCH_SCAN based on:\n- Content structure and formatting consistency\n- Document flow and topic coherence\n- Presence of multiple document headers/footers\n- Format changes and scan artifacts\n\nRESPONSE FORMAT:\nCLASSIFICATION: [SINGLE_DOCUMENT or BATCH_SCAN]\nCONFIDENCE: [0-100]\nREASONING: [Detailed explanation of your analysis]\n\nProvide your analysis now:"""
        )
        
        logging.info(f"🤖 Sending request to Ollama for {filename}")
        response = _query_ollama(prompt, timeout=app_config.OLLAMA_TIMEOUT, context_window=app_config.OLLAMA_CTX_CATEGORY, task_name="document_type_analysis")
        
        if not response:
            logging.warning(f"🤖 No response from Ollama for {filename}")
            return None
            
        logging.info(f"🤖 Received response from Ollama for {filename}: {len(response)} characters")
        classification = None
        confidence = 0
        reasoning = None
        lines = response.strip().split('\n')
        logging.debug(f"Raw LLM response for {filename}: {response}")
        for line in lines:
            line = line.strip()
            if line.startswith('CLASSIFICATION:') or line.startswith('**CLASSIFICATION:**'):
                classification_text = line.split(':', 1)[1].strip().replace('*', '').upper()
                if 'SINGLE_DOCUMENT' in classification_text or 'SINGLE' in classification_text:
                    classification = 'single_document'
                elif 'BATCH_SCAN' in classification_text or 'BATCH' in classification_text:
                    classification = 'batch_scan'
            elif line.startswith('CONFIDENCE:') or line.startswith('**CONFIDENCE:**'):
                try:
                    conf_text = line.split(':', 1)[1].strip().replace('*', '')
                    confidence = int(''.join(filter(str.isdigit, conf_text)))
                    confidence = max(0, min(100, confidence))
                except (ValueError, IndexError):
                    confidence = 50
            elif line.startswith('REASONING:') or line.startswith('**REASONING:**'):
                reasoning = line.split(':', 1)[1].strip().replace('*', '')
            elif reasoning is not None and line and not line.startswith(('CLASSIFICATION:', 'CONFIDENCE:', '**CLASSIFICATION:**', '**CONFIDENCE:**')):
                reasoning += " " + line
        if classification:
            if not reasoning:
                reasoning = "No explanation provided by LLM. Please check prompt or model configuration."
            result = {
                'classification': classification,
                'confidence': confidence,
                'reasoning': reasoning,
                'llm_used': True
            }
            logging.info(f"✅ Document analysis SUCCESS for {filename} - Type: {classification}, Confidence: {confidence}%")
            logging.debug(f"✅ LLM reasoning: {reasoning}")
            return result
        else:
            logging.warning(f"❌ Could not parse LLM response for {filename}: {response[:200]}...")
            logging.debug(f"❌ Full unparseable response: {response}")
            return None
    except Exception as e:
        logging.error(f"💥 Error getting LLM document type analysis for {filename}: {e}")
        import traceback
        logging.debug(f"💥 Full traceback: {traceback.format_exc()}")
        return None

def _query_ollama(prompt: str, timeout: int = 45, context_window: int = 4096, task_name: str = "general") -> Optional[str]:
    """
    Queries the Ollama LLM with the given prompt.
    """
    logging.info(f"🌐 _query_ollama called for task: {task_name}")
    logging.debug(f"🌐 Ollama config: host={app_config.OLLAMA_HOST}, model={app_config.OLLAMA_MODEL}")
    
    if not app_config.OLLAMA_HOST or not app_config.OLLAMA_MODEL:
        logging.error(f"❌ Ollama not configured - OLLAMA_HOST={app_config.OLLAMA_HOST}, OLLAMA_MODEL={app_config.OLLAMA_MODEL}")
        return None
        
    try:
        import ollama
        logging.debug(f"🌐 Creating Ollama client for {app_config.OLLAMA_HOST}")
        client = ollama.Client(host=app_config.OLLAMA_HOST)
        
        messages = [{'role': 'user', 'content': prompt}]
        options = {'num_ctx': context_window}
        
        logging.info(f"🌐 Sending {task_name} request to Ollama model {app_config.OLLAMA_MODEL} (timeout: {timeout}s)")
        logging.debug(f"🌐 Request options: {options}")
        
        response = client.chat(
            model=app_config.OLLAMA_MODEL,
            messages=messages,
            options=options
        )
        
        result = response['message']['content'].strip()
        logging.info(f"✅ Ollama {task_name} response received: {len(result)} characters")
        logging.debug(f"✅ Response preview: {result[:200]}{'...' if len(result) > 200 else ''}")
        return result
        
    except ImportError as ie:
        logging.error(f"❌ ollama package not installed - run: pip install ollama. Error: {ie}")
        return None
    except Exception as e:
        logging.error(f"💥 Error querying Ollama for {task_name}: {e}")
        import traceback
        logging.debug(f"💥 Full traceback: {traceback.format_exc()}")
        return None

