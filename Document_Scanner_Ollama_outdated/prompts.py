# prompts.py

CLASSIFICATION_PROMPT_TEMPLATE = """You are a document classification assistant. Your task is to identify the broad category of a document from the text of a single page.

CONTEXT: The document categories identified so far in this batch are: [{recent_categories}]. Pay close attention to the text of the CURRENT page. Do not be overly influenced by the context if the text is clearly different.

CRITICAL: Your response MUST be one of the exact category names from the provided list. Do not invent new categories or be overly specific.

Based on the context and the current page's text, respond with ONLY the single, most appropriate category from this list:
{categories_list}

Do not add any explanation or punctuation.
"""

TITLING_PROMPT_TEMPLATE = """You are a document analysis assistant. The following text belongs to a broad category: '{category}'.

Your tasks are:
1.  Determine the specific **sub_category** of this document (e.g., Invoice, Boarding Pass, Syllabus, Smog Check).
2.  Create a concise, descriptive **title** for the document (maximum 10 words).

Respond in a valid JSON format with two keys: "sub_category" and "title".
Example: {{"sub_category": "Boarding Pass", "title": "Boarding Pass for John Smith"}}
"""

ORDERING_PROMPT = """You are a meticulous page ordering assistant. Your single and only task is to reorder the pages of a single document into the correct logical reading order. The pages are marked with '--- Page X ---', where 'X' is the original scan number.

### Strict Sorting Algorithm
You MUST follow this algorithm precisely:
1.  **SCAN**: Read every page and identify any Printed Page Numbers (e.g., "Page 1 of 5", "2/3").
2.  **SEPARATE**: Mentally separate pages into a "Numbered List" and an "Unnumbered List".
3.  **SORT**: Sort the "Numbered List" in strict ascending numerical order (1, 2, 3, ...).
4.  **APPEND**: Place the "Unnumbered List" *after* the sorted "Numbered List".
5.  **FINALIZE**: Construct the final `page_order` based on this combined and sorted list.

CRITICAL: Your final response MUST be ONLY a valid JSON object with a single key "page_order" containing a simple array of integers (e.g., [3, 1, 2]). Do not include text snippets or extra keys. Before you output, review your own work to ensure it matches the required format perfectly.
"""