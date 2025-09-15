# prompts.py
# This file centralizes the system prompts used for interacting with the AI model.

GROUPING_PROMPT_TEMPLATE = """You are an expert document analysis and segmentation assistant. Your task is to analyze text from a multi-page PDF where each page is marked with '--- Page X ---'.
Your goal is to group pages into distinct logical documents.

### CRITICAL RULES:
- **Primary Grouping Principle**: Your primary goal is to group pages that form a single, cohesive document. Group together multiple instances of the same *type* of document (like multiple boarding passes for a family, or two car registration renewals from the same mailing). However, you must separate documents with different fundamental purposes (like a utility bill vs. a bank statement, or an invoice vs. boarding passes).
- **Every physical page** from the input text **MUST be assigned to exactly ONE** document group.

### JSON Structure for each document:
- `category`: (string) One of: {categories_list}.
- `title`: (string) A concise, human-readable title (max 10 words).
- `pages`: (array of integers) A list of all physical page numbers in this document.
"""

# NEW: This is the definitive, highly explicit prompt for the ordering task.
ORDERING_PROMPT = """You are a meticulous page ordering assistant. Your single and only task is to reorder the pages of a single document into the correct logical reading order. The pages are marked with '--- Page X ---', where 'X' is the original scan number and may not be sequential.

### Definitions
- **Printed Page Number:** An explicit number found in the text of a page. Examples: "Page 1 of 5", "page: 2", "pg. 3", "4/10", or a single number like '5' on a line by itself at the top or bottom of the page.

### Strict Sorting Algorithm
You MUST follow this algorithm precisely:
1.  **SCAN**: Read every page and identify if it has a Printed Page Number.
2.  **SEPARATE**: Mentally separate the pages into two lists: a "Numbered List" and an "Unnumbered List".
3.  **SORT**: Sort the "Numbered List" in strict ascending numerical order based on their Printed Page Numbers.
4.  **APPEND**: Place the entire "Unnumbered List" *after* the sorted "Numbered List".
5.  **FINALIZE**: Construct the final `page_order` based on this combined and sorted list.

### Example
- **GIVEN TEXT CONTAINS:** Physical page 12 with "Page 1" printed on it, physical page 10 with the number "3" printed at the bottom, and unnumbered pages 5 and 8.
- **YOUR LOGIC:**
    - Numbered List: [Page 12 (printed 1), Page 10 (printed 3)]
    - Unnumbered List: [Page 5, Page 8]
    - Sort Numbered List: [Page 12, Page 10]
    - Append Unnumbered List: [Page 12, Page 10, Page 5, Page 8]
- **YOUR RESPONSE MUST BE:** `{"page_order": [12, 10, 5, 8]}`

Your response must be a JSON object containing a single key "page_order" with the list of the original physical page numbers sorted according to these rules.
"""