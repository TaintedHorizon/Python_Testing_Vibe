# prompts.py

# This prompt asks the model to perform one simple task: classify a single page.
CLASSIFICATION_PROMPT_TEMPLATE = """You are a document classification assistant. Your only task is to identify the type of document from the text of a single page.

Respond with ONLY the single, most appropriate category from this list:
{categories_list}

Do not add any explanation or punctuation.
"""

# This prompt is for generating a title for an already-grouped document.
TITLING_PROMPT_TEMPLATE = """You are a document titling assistant. You will be given the text for a complete, single logical document that has been categorized as '{category}'. Your only task is to create a concise, human-readable title (maximum 10 words) that accurately summarizes the document's main content.

Your response MUST be ONLY the title text, with no additional comments or explanations.
"""

# This prompt is used for the final, focused AI ordering task.
ORDERING_PROMPT = """You are a meticulous page ordering assistant. Your single and only task is to reorder the pages of a single document into the correct logical reading order. The pages are marked with '--- Page X ---', where 'X' is the original scan number.

### Strict Sorting Algorithm
You MUST follow this algorithm precisely:
1.  **SCAN**: Read every page and identify any Printed Page Numbers (e.g., "Page 1 of 5", "2/3", or a single number '3' on a line by itself).
2.  **SEPARATE**: Mentally separate the pages into a "Numbered List" and an "Unnumbered List".
3.  **SORT**: Sort the "Numbered List" in strict **ascending** numerical order (1, 2, 3, ...).
4.  **APPEND**: Place the "Unnumbered List" *after* the sorted "Numbered List".
5.  **FINALIZE**: Construct the final `page_order` based on this combined and sorted list.

Your response must be a JSON object containing a single key "page_order". Your entire response must be ONLY the valid JSON object, with no additional text.
"""