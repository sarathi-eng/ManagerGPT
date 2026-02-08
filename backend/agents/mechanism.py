import json
from ..utils.llm import call_llm
from ..utils.parse_llm_json import parse_llm_json


async def extract_mechanism(goal: str, context: dict):
    prompt = f"""
You are an operations strategist.

Business:
{goal}

Industry:
{context['industry']}

Your task:
Identify what ACTUALLY changes inside the business if this decision is made.

Focus only on internal mechanics:
- revenue stability
- labor utilization
- capacity usage
- inventory waste
- customer behavior pattern

DO NOT mention market size
DO NOT give advice
DO NOT use examples from other industries

Return JSON:
{{
  "core_mechanism": "one sentence",
  "affected_variables": ["var1","var2","var3"]
}}
"""
    res = await call_llm(prompt, temperature=0)
    return parse_llm_json(res)
