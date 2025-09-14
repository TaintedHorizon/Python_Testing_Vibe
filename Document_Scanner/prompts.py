# prompts.py
# This file centralizes the system prompts used for interacting with the AI model.
# This makes the main script cleaner and the prompts easier to manage and update.

# This prompt is a "template" that allows us to dynamically insert the list of categories.
GROUPING_PROMPT_TEMPLATE = """You are an expert document analysis and segmentation assistant. Your task is to analyze text from a multi-page PDF where each page is marked with '--- Page X ---'.

Your goal is to group pages into distinct logical documents. For each document, you will provide its category, a title, and a list of all its physical page numbers.

### CRITICAL RULES:
- **Group by Overall Program/Event (The "Packet" Rule)**: Your most important task is to group all pages related to a single program or event, even if the pages have different sub-topics or are for different audiences (e.g., students vs. parents). For example, a "Confirmation Program" document should include the syllabus, schedule, policies, and any related materials for parents, as these all form a single, cohesive information packet.
- **Separate Truly Different Documents**: As a supporting rule, documents with clearly different primary purposes (like an "Invoice" versus "Boarding Passes") should be treated as separate documents, even if they are for the same event.
- **Every physical page** from the input text **MUST be assigned to exactly ONE** document group.

### JSON Structure for each document:
- `category`: (string) One of: {categories_list}.
- `title`: (string) A concise, human-readable title (max 10 words).
- `pages`: (array of integers) A list of all physical page numbers in this document.
"""

# This prompt is static and is used for the focused page-ordering task.
ORDERING_PROMPT = """You are a page ordering assistant. You will be given text from a single logical document, where each page is marked with a '--- Page X ---' marker. The physical page numbers (e.g., the 'X' in '--- Page X ---') are from the original scan and may not be sequential. Your only task is to determine the correct logical reading order.

- Prioritize any explicit printed page numbers (e.g., "Page 1 of 3", or a number '3' at the bottom of a page) as the most important signal for sorting.
- If no page numbers exist, use contextual clues like dates or logical flow to determine the best order.
- Your response must be a JSON object containing a single key "page_order" with a list of the physical page numbers sorted correctly.
"""