import logging
import os
from typing import Optional, Dict, List

try:
    from .config_manager import app_config
except ImportError:
    # Handle direct script execution
    from config_manager import app_config


def extract_document_tags(ocr_text: str, document_name: str = "") -> Optional[Dict[str, List[str]]]:
    """
    Extracts structured tags from document text using LLM analysis.
    Returns categorized tags for enhanced searchability and RAG enrichment.
    
    Args:
        ocr_text: Full OCR text from the document
        document_name: Optional document name for context
        
    Returns:
        Dictionary with categorized tags or None if extraction fails
        Format: {
            'people': ['John Doe', 'Jane Smith'],
            'organizations': ['Acme Corp', 'ABC Bank'],
            'places': ['New York', 'Main Street'],
            'dates': ['2023-12-15', 'December 2023'],
            'document_types': ['invoice', 'contract'],
            'keywords': ['payment', 'agreement', 'finance'],
            'amounts': ['$1,200.00', '$500'],
            'reference_numbers': ['INV-2023-001', 'REF123']
        }
    """
    logging.info(f"🏷️  Extracting tags for document: {document_name or 'unnamed'}")
    
    if not ocr_text or len(ocr_text.strip()) < 50:
        logging.warning(f"🏷️  Insufficient text for tag extraction: {len(ocr_text)} characters")
        return None
    
    try:
        prompt = f"""Analyze this document text and extract relevant tags for search and categorization.

DOCUMENT: {document_name}

TEXT TO ANALYZE:
{ocr_text[:6000]}

EXTRACT THE FOLLOWING TAG CATEGORIES:

**PEOPLE**: Full names of individuals mentioned (avoid titles, extract: "John Smith" not "Mr. Smith")
**ORGANIZATIONS**: Company names, institutions, agencies, banks (full legal names when possible)
**PLACES**: Cities, states, countries, addresses, landmarks (be specific: "123 Main St, Boston MA" not just "Main St")
**DATES**: Specific dates, months, years found in text (format as found: "Dec 15, 2023" or "2023-12-15")
**DOCUMENT_TYPES**: What type of document this appears to be (invoice, contract, letter, report, etc.)
**KEYWORDS**: Important subject matter terms (industry terms, topics, legal terms, financial terms)
**AMOUNTS**: Dollar amounts, quantities, percentages (include currency symbol: "$1,200.00")
**REFERENCE_NUMBERS**: Account numbers, invoice numbers, case numbers, ID numbers (format as found)

RULES:
1. Only extract tags that are explicitly mentioned in the text
2. Be precise - avoid generic terms like "company" or "person"
3. For amounts, include the full value with currency/units
4. For places, include full addresses when available
5. For dates, preserve the original format found in the document
6. Maximum 8 items per category
7. If a category has no relevant items, return an empty list

RESPONSE FORMAT (JSON-like structure):
PEOPLE: [name1, name2, ...]
ORGANIZATIONS: [org1, org2, ...]
PLACES: [place1, place2, ...]
DATES: [date1, date2, ...]
DOCUMENT_TYPES: [type1, type2, ...]
KEYWORDS: [keyword1, keyword2, ...]
AMOUNTS: [amount1, amount2, ...]
REFERENCE_NUMBERS: [ref1, ref2, ...]

Extract tags now:"""
        
        logging.debug(f"🏷️  Sending tag extraction request for {document_name}")
        response = _query_ollama(
            prompt,
            timeout=app_config.OLLAMA_TIMEOUT,
            context_window=getattr(app_config, 'OLLAMA_CTX_TAGGING', getattr(app_config, 'OLLAMA_CTX_TITLE_GENERATION', 4096)),
            task_name="tag_extraction"
        )
        
        if not response:
            logging.warning(f"🏷️  No response from LLM for tag extraction: {document_name}")
            return None
            
        # Parse the response into structured tags
        tags = {
            'people': [],
            'organizations': [],
            'places': [],
            'dates': [],
            'document_types': [],
            'keywords': [],
            'amounts': [],
            'reference_numbers': []
        }
        
        lines = response.strip().split('\n')
        current_category = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Check for category headers
            for category in tags.keys():
                category_upper = category.upper().replace('_', '_')
                if line.startswith(f"{category_upper}:") or line.startswith(f"**{category_upper}**:"):
                    current_category = category
                    # Extract items from the same line if present
                    content = line.split(':', 1)[1].strip() if ':' in line else ''
                    if content and content not in ['[]', '[ ]']:
                        # Parse list format: [item1, item2, item3]
                        if content.startswith('[') and content.endswith(']'):
                            content = content[1:-1]
                        items = [item.strip().strip('"\'') for item in content.split(',') if item.strip()]
                        tags[category].extend([item for item in items if item and len(item) > 1])
                    break
            else:
                # If we're in a category and this line contains items
                if current_category and line and not line.startswith(('PEOPLE:', 'ORGANIZATIONS:', 'PLACES:', 'DATES:', 'DOCUMENT_TYPES:', 'KEYWORDS:', 'AMOUNTS:', 'REFERENCE_NUMBERS:')):
                    # Handle continuation lines or list items
                    if line.startswith(('[', '-', '•')):
                        items = line.strip('[]- •').split(',')
                        items = [item.strip().strip('"\'') for item in items if item.strip()]
                        tags[current_category].extend([item for item in items if item and len(item) > 1])
        
        # Clean up and limit tags
        for category in tags:
            # Remove duplicates while preserving order
            seen = set()
            tags[category] = [item for item in tags[category] if item not in seen and not seen.add(item)]
            # Limit to 8 items per category
            tags[category] = tags[category][:8]
        
        # Count total tags extracted
        total_tags = sum(len(tag_list) for tag_list in tags.values())
        
        if total_tags > 0:
            logging.info(f"✅ Tag extraction SUCCESS for {document_name}: {total_tags} total tags")
            logging.debug(f"✅ Extracted tags: {tags}")
            return tags
        else:
            logging.warning(f"⚠️  No tags extracted from document: {document_name}")
            logging.debug(f"⚠️  LLM response was: {response[:300]}...")
            return None
            
    except Exception as e:
        logging.error(f"💥 Error extracting tags for {document_name}: {e}")
        import traceback
        logging.debug(f"💥 Full traceback: {traceback.format_exc()}")
        return None
def get_ai_document_type_analysis(file_path: str, content_sample: str, filename: str, page_count: int, file_size_mb: float) -> Optional[dict]:
    """
    Uses LLM to analyze document type based on content and metadata.
    Returns dict with classification, confidence, reasoning, and llm_used flag.
    """
    logging.info(f"🤖 get_ai_document_type_analysis called for {filename}")
    logging.debug(f"🤖 Parameters: pages={page_count}, size={file_size_mb}MB, content_len={len(content_sample)}")
    
    try:
        prompt = (
            f"""You are a document analysis expert. Analyze this document and determine if it should be processed as a SINGLE_DOCUMENT or BATCH_SCAN.

FILE DETAILS:
- Filename: {filename}
- Page Count: {page_count}
- File Size: {file_size_mb:.1f} MB

DOCUMENT CONTENT SAMPLES:
{content_sample[:4000]}

ANALYSIS TASK:
Classify as SINGLE_DOCUMENT or BATCH_SCAN based on:

FOR SINGLE_DOCUMENT (one coherent document):
- Consistent formatting, headers, and style across all sampled pages
- Logical content flow and topic continuity
- Same company/organization throughout
- Sequential page numbering or logical progression
- No abrupt topic/format changes between pages

FOR BATCH_SCAN (multiple documents scanned together):
- Different company headers/letterheads between pages
- Abrupt topic changes (invoice → personal letter → receipt)
- Inconsistent formatting styles between pages
- Multiple document types mixed together
- Content that doesn't logically connect between pages

CRITICAL: Pay special attention to transitions between page samples. Look for signs of document boundaries like:
- Company name changes
- Format style shifts
- Topic discontinuity
- Different document types

RESPONSE FORMAT:
CLASSIFICATION: [SINGLE_DOCUMENT or BATCH_SCAN]
CONFIDENCE: [0-100]
REASONING: [Detailed explanation focusing on consistency/discontinuity between pages]

Provide your analysis now:"""
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
        import requests

        # Safely derive a numeric num_gpu value from env or app_config
        env_num_gpu = os.getenv('OLLAMA_NUM_GPU')
        if env_num_gpu is not None:
            try:
                num_gpu_val = int(env_num_gpu)
            except Exception:
                num_gpu_val = 0
        else:
            try:
                num_gpu_val = int(getattr(app_config, 'OLLAMA_NUM_GPU', 0))
            except Exception:
                num_gpu_val = 0

        options = {'num_ctx': context_window, 'num_gpu': num_gpu_val}

        logging.info(f"🌐 Sending {task_name} request to Ollama model {app_config.OLLAMA_MODEL} (timeout: {timeout}s) num_gpu={num_gpu_val}")
        logging.debug(f"🌐 Request options: {options}")

        # First attempt: use the Python client library (preferred)
        try:
            client = ollama.Client(host=app_config.OLLAMA_HOST)
            messages = [{'role': 'user', 'content': prompt}]
            response = client.chat(
                model=app_config.OLLAMA_MODEL,
                messages=messages,
                options=options,
            )
            # Extract content if present
            try:
                msg = getattr(response, 'message', None)
                content = getattr(msg, 'content', None) if msg is not None else None
                result = content.strip() if isinstance(content, str) else str(response)
            except Exception:
                result = str(response)

            # Validate result is non-empty string
            if not result or not isinstance(result, str):
                raise ValueError('Empty or invalid response from ollama.Client.chat')

            logging.info(f"✅ Ollama (client) {task_name} response received: {len(result)} characters")
            logging.debug(f"✅ Response preview: {result[:200]}{'...' if len(result) > 200 else ''}")
            return result
        except Exception as client_ex:
            logging.warning(f"⚠️ Ollama client.chat failed or returned invalid response, falling back to HTTP generate: {client_ex}")
            logging.debug("⚠️ Client exception traceback:", exc_info=True)

        # Fallback: call the HTTP /api/generate endpoint with the same options
        try:
            payload = {
                'model': app_config.OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': options,
            }
            url = app_config.OLLAMA_HOST.rstrip('/') + '/api/generate'
            resp = requests.post(url, json=payload, timeout=(3, timeout))
            resp.raise_for_status()
            data = resp.json()
            result = data.get('response') or data.get('message', {}).get('content') or ''
            result = result.strip() if isinstance(result, str) else str(result)
            logging.info(f"✅ Ollama (http) {task_name} response received: {len(result)} characters")
            logging.debug(f"✅ HTTP Response preview: {result[:200]}{'...' if len(result) > 200 else ''}")
            return result
        except Exception as http_ex:
            logging.error(f"💥 Ollama HTTP fallback failed for {task_name}: {http_ex}")
            logging.debug("💥 HTTP fallback traceback:", exc_info=True)
            return None
        
    except ImportError as ie:
        logging.error(f"❌ ollama package not installed - run: pip install ollama. Error: {ie}")
        return None
    except Exception as e:
        logging.error(f"💥 Error querying Ollama for {task_name}: {e}")
        import traceback
        logging.debug(f"💥 Full traceback: {traceback.format_exc()}")
        return None

