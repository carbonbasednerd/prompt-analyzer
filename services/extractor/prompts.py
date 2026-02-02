"""Extraction prompts for LLM."""


def build_extraction_prompt(text: str) -> str:
    """Build extraction prompt for LLM."""
    return f"""You are a semantic claim extractor. Your job is to extract explicit rules and instructions from text.

RULES:
1. Only extract explicitly stated rules
2. Include verbatim evidence (quote exact text)
3. Return JSON only
4. If ambiguous, return empty list or low confidence
5. Use descriptive action names (e.g., "file_write", "internet_access", "tool_use", "modify_prod")
6. Use only these modalities: must, must_not, should, prefer, avoid, allowed

INPUT: {text}

OUTPUT: List of claims in this exact format (return ONLY the JSON array, no other text):
[{{
  "modality": "...",
  "action": "...",
  "target": "...",
  "conditions": [],
  "exceptions": [],
  "confidence": 0.0,
  "evidence": ["exact quote"]
}}]

Examples:
- "Never modify production files" → {{"modality": "must_not", "action": "file_write", "target": "production files", "conditions": [], "exceptions": [], "confidence": 0.95, "evidence": ["Never modify production files"]}}
- "Use verbose logging" → {{"modality": "should", "action": "set_verbosity", "target": "logging", "conditions": [], "exceptions": [], "confidence": 0.9, "evidence": ["Use verbose logging"]}}
- "Don't access internet unless needed" → {{"modality": "must_not", "action": "internet_access", "target": "external services", "conditions": [], "exceptions": ["unless needed"], "confidence": 0.85, "evidence": ["Don't access internet unless needed"]}}

If the action doesn't fit common categories, create a descriptive action name.
If no rules found, return: []

Remember: Return ONLY the JSON array, no explanations or markdown.
"""
