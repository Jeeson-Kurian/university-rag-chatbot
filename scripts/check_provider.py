"""Diagnose the OPENAI_API_KEY without revealing it: shape of the value + one tiny API call."""
import os
import sys

raw = os.getenv("OPENAI_API_KEY")
if raw is None:
    print("OPENAI_API_KEY is not set in this job."); sys.exit(2)
key = raw.strip()
print(f"length={len(raw)} (stripped {len(key)}); starts_with={key[:8].split('-')[0]+'-' if '-' in key[:8] else key[:3]!r}"
      f"; whitespace_or_newline={raw != key or any(c.isspace() for c in key)}"
      f"; quotes={key[:1] in '\"' + chr(39) or key[-1:] in '\"' + chr(39)}"
      f"; looks_masked={'*' in key or '...' in key}")
from openai import OpenAI
try:
    models = OpenAI(api_key=key, max_retries=0, timeout=20).models.list()
    print("OK: key accepted; models visible:", len(list(models)))
except Exception as exc:
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None) or {}
    code = body.get("code") if isinstance(body, dict) else None
    print(f"FAILED: {type(exc).__name__} status={status} code={code}")
    sys.exit(1)
try:
    r = OpenAI(api_key=key, max_retries=0, timeout=20).chat.completions.create(
        model="gpt-4o-mini", messages=[{"role": "user", "content": "Say OK"}], max_tokens=3)
    print("OK: chat call works:", r.choices[0].message.content)
except Exception as exc:
    body = getattr(exc, "body", None) or {}
    print(f"CHAT FAILED: {type(exc).__name__} status={getattr(exc, 'status_code', None)} "
          f"code={body.get('code') if isinstance(body, dict) else None}")
    sys.exit(1)
