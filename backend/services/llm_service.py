import httpx
import json
import time
import math
import statistics
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
)


def _geo_mean_token_prob_from_logprobs(entries: Optional[List[Any]]) -> tuple[Optional[float], int]:
    """
    Geometric mean of completion-token probabilities: exp(mean(logprob)).
    
    Args:
        entries: list of dicts with a numeric 'logprob' (natural log), Ollama-style.
    
    Returns:
        tuple of (confidence, number of tokens used)
    """
    values: List[float] = []
    for e in entries or []:
        if not isinstance(e, dict):
            continue
        lp = e.get("logprob")
        if lp is None:
            continue
        try:
            x = float(lp)
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            values.append(x)
    if not values:
        return None, 0
    mean_lp = statistics.mean(values)
    conf = math.exp(mean_lp)
    conf = max(0.0, min(1.0, conf))
    return conf, len(values)


@dataclass
class LLMResponse:
    """Response from LLM."""
    raw_response: str
    parsed_response: Optional[Dict[str, Any]]
    model_used: str
    processing_time_ms: int
    tokens_used: Optional[int] = None
    confidence_from_logprobs: Optional[float] = None
    logprob_token_count: int = 0


class LLMService:
    """Service for LLM operations using Ollama."""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model
        self.timeout = 120.0  # 2 minutes timeout for LLM calls
        self.ollama_debug = os.getenv("OLLAMA_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
        self.ollama_debug_max_chars = int(os.getenv("OLLAMA_DEBUG_MAX_CHARS", "4000"))
        self.openrouter_debug = os.getenv("OPENROUTER_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
        self.openrouter_debug_max_chars = int(os.getenv("OPENROUTER_DEBUG_MAX_CHARS", "4000"))
    
    def _dbg(self, label: str, text: str):
        if not self.ollama_debug:
            return
        try:
            s = text or ""
            if len(s) > self.ollama_debug_max_chars:
                s = s[: self.ollama_debug_max_chars] + "\n... [truncated] ..."
            print(f"\n[OLLAMA DEBUG] {label}\n{s}\n")
        except Exception:
            pass

    def _dbg_openrouter(self, label: str, text: str):
        if not self.openrouter_debug:
            return
        try:
            s = text or ""
            if len(s) > self.openrouter_debug_max_chars:
                s = s[: self.openrouter_debug_max_chars] + "\n... [truncated] ..."
            print(f"\n[OPENROUTER DEBUG] {label}\n{s}\n")
        except Exception:
            pass

    def _compact_block(self, text: str) -> str:
        """Compact user-provided text blocks to reduce prompt noise."""
        s = (text or "").strip()
        if not s:
            return ""
        # Normalize newlines and collapse excessive blank lines
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        while "\n\n\n" in s:
            s = s.replace("\n\n\n", "\n\n")
        # For OCR / PDF-derived text, single newlines are often just line wraps.
        # Preserve paragraph breaks (double newlines), but flatten single newlines to spaces.
        parts = [p.strip() for p in s.split("\n\n")]
        flattened = []
        for p in parts:
            p = " ".join(p.splitlines())
            p = " ".join(p.split())
            if p:
                flattened.append(p)
        s = "\n\n".join(flattened)
        return s

    def _compact_student_answer(self, text: str) -> str:
        """
        Compact student answers while preserving list structure.
        Unlike `_compact_block`, we try NOT to merge separate points into one line,
        because that makes evidence extraction/counting unreliable.
        """
        s = (text or "").strip()
        if not s:
            return ""
        s = s.replace("\r\n", "\n").replace("\r", "\n")
        while "\n\n\n" in s:
            s = s.replace("\n\n\n", "\n\n")
        # Treat common separators as item boundaries.
        s = s.replace("•", "\n").replace("·", "\n")
        s = re.sub(r"[;,]\s*", "\n", s)
        s = re.sub(r"\.\s+", "\n", s)
        # Normalize lines
        lines = []
        for line in s.splitlines():
            line = " ".join(line.split()).strip()
            if line:
                lines.append(line)
        # Keep at most a reasonable number of lines to avoid prompt bloat.
        return "\n".join(lines[:30])
    
    async def _call_ollama(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        request_completion_logprobs: bool = False,
    ) -> LLMResponse:
        """
        Call Ollama API.
        
        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            
        Returns:
            LLMResponse object
        """
        start_time = time.time()
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Lower for more consistent outputs
                "num_predict": 2048
            }
        }
        if request_completion_logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = 0

        if self.ollama_debug:
            try:
                safe_payload = {
                    "model": payload.get("model"),
                    "stream": payload.get("stream"),
                    "options": payload.get("options"),
                    "messages": payload.get("messages"),
                }
                self._dbg("Request payload (api/chat)", json.dumps(safe_payload, indent=2, ensure_ascii=False))
            except Exception:
                pass
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            if request_completion_logprobs and response.status_code == 400:
                payload_retry = {k: v for k, v in payload.items() if k not in ("logprobs", "top_logprobs")}
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload_retry
                )
            response.raise_for_status()
            result = response.json()
        
        processing_time = int((time.time() - start_time) * 1000)
        raw_response = result.get("message", {}).get("content", "")
        
        if self.ollama_debug:
            try:
                meta = {
                    "model": result.get("model"),
                    "eval_count": result.get("eval_count"),
                    "eval_duration": result.get("eval_duration"),
                    "prompt_eval_count": result.get("prompt_eval_count"),
                    "prompt_eval_duration": result.get("prompt_eval_duration"),
                    "total_duration": result.get("total_duration"),
                }
                self._dbg("Response meta", json.dumps(meta, indent=2, ensure_ascii=False))
                self._dbg("Raw response content", raw_response)
            except Exception:
                pass
        
        # Try to parse JSON from response
        parsed = self._try_parse_json(raw_response)

        conf_lp: Optional[float] = None
        lp_n = 0
        if request_completion_logprobs:
            raw_lp = result.get("logprobs")
            conf_lp, lp_n = _geo_mean_token_prob_from_logprobs(raw_lp if isinstance(raw_lp, list) else None)

        return LLMResponse(
            raw_response=raw_response,
            parsed_response=parsed,
            model_used=self.model,
            processing_time_ms=processing_time,
            tokens_used=result.get("eval_count"),
            confidence_from_logprobs=conf_lp,
            logprob_token_count=lp_n,
        )

    async def _call_openrouter(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model_override: Optional[str] = None,
        request_completion_logprobs: bool = False,
    ) -> LLMResponse:
        """Call OpenRouter chat completions API."""
        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY is not configured")

        start_time = time.time()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        model_name = (model_override or OPENROUTER_MODEL).strip()
        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.1,
        }
        if request_completion_logprobs:
            payload["logprobs"] = True
            payload["top_logprobs"] = 0
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

        if self.openrouter_debug:
            try:
                safe_headers = {
                    "Authorization": "Bearer ***",
                    "Content-Type": headers.get("Content-Type"),
                }
                safe_payload = {
                    "model": payload.get("model"),
                    "temperature": payload.get("temperature"),
                    "messages": payload.get("messages"),
                    "logprobs": payload.get("logprobs"),
                    "top_logprobs": payload.get("top_logprobs"),
                }
                self._dbg_openrouter("Request URL", f"{OPENROUTER_BASE_URL}/chat/completions")
                self._dbg_openrouter("Request headers", json.dumps(safe_headers, indent=2, ensure_ascii=False))
                self._dbg_openrouter("Request payload", json.dumps(safe_payload, indent=2, ensure_ascii=False))
            except Exception:
                pass

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )
            if request_completion_logprobs and response.status_code == 400:
                payload_retry = {k: v for k, v in payload.items() if k not in ("logprobs", "top_logprobs")}
                response = await client.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload_retry
                )
            if self.openrouter_debug and response.status_code >= 400:
                try:
                    self._dbg_openrouter(
                        f"HTTP error response ({response.status_code})",
                        response.text or "",
                    )
                except Exception:
                    pass
            response.raise_for_status()
            result = response.json()

        processing_time = int((time.time() - start_time) * 1000)
        raw_response = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = self._try_parse_json(raw_response)
        tokens = (result.get("usage", {}) or {}).get("total_tokens")

        conf_lp: Optional[float] = None
        lp_n = 0
        if request_completion_logprobs:
            choice = (result.get("choices") or [{}])[0]
            lp_obj = choice.get("logprobs") or {}
            content = lp_obj.get("content")
            conf_lp, lp_n = _geo_mean_token_prob_from_logprobs(content if isinstance(content, list) else None)

        if self.openrouter_debug:
            try:
                meta = {
                    "model": result.get("model"),
                    "provider": result.get("provider"),
                    "usage": result.get("usage"),
                    "id": result.get("id"),
                    "processing_time_ms": processing_time,
                }
                self._dbg_openrouter("Response meta", json.dumps(meta, indent=2, ensure_ascii=False))
                self._dbg_openrouter("Raw response content", raw_response)
            except Exception:
                pass

        return LLMResponse(
            raw_response=raw_response,
            parsed_response=parsed,
            model_used=model_name,
            processing_time_ms=processing_time,
            tokens_used=tokens,
            confidence_from_logprobs=conf_lp,
            logprob_token_count=lp_n,
        )
    
    def _try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract and parse JSON from response text."""
        # Try direct parse
        try:
            return json.loads(text)
        except:
            pass
        
        # Try to find JSON in markdown code block
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except:
                pass
        
        # Try to find JSON object/array in text
        for start_char, end_char in [('{', '}'), ('[', ']')]:
            start = text.find(start_char)
            if start != -1:
                # Find matching end
                depth = 0
                for i, char in enumerate(text[start:], start):
                    if char == start_char:
                        depth += 1
                    elif char == end_char:
                        depth -= 1
                        if depth == 0:
                            try:
                                return json.loads(text[start:i+1])
                            except:
                                break
        
        return None
    
    async def cleanup_ocr_text(self, raw_text: str) -> LLMResponse:
        """
        Clean up and correct OCR text using LLM.
        
        Args:
            raw_text: Raw OCR output
            
        Returns:
            LLMResponse with cleaned text
        """
        system_prompt = """You are an expert OCR text cleaner. Return ONLY valid JSON with exactly one key:
{"corrected_text":"..."}

Rules:
- Fix OCR character errors and obvious spelling/grammar mistakes.
- Keep original meaning.
- Preserve numbering, labels, and line breaks where possible.
- Do not add any keys besides corrected_text.
- Do not include markdown, comments, or extra text."""

        prompt = f"""Clean this OCR text and return JSON only:
        
OCR_TEXT_START 
{raw_text} 
OCR_TEXT_END"""

        result = await self._call_ollama(prompt, system_prompt)
        parsed = result.parsed_response if isinstance(result.parsed_response, dict) else None
        corrected = ""
        if parsed:
            corrected = str(parsed.get("corrected_text") or "").strip()

        # Keep raw_response as normalized corrected text for downstream callers.
        # If JSON parse fails, safely fall back to the model raw output.
        final_text = corrected or (result.raw_response or "").strip()
        return LLMResponse(
            raw_response=final_text,
            parsed_response=parsed,
            model_used=result.model_used,
            processing_time_ms=result.processing_time_ms,
            tokens_used=result.tokens_used,
            confidence_from_logprobs=result.confidence_from_logprobs,
            logprob_token_count=result.logprob_token_count,
        )
    
    async def grade_answer(
        self,
        question: str,
        answer_scheme: str,
        student_answer: str,
        max_marks: float,
        provider: str = "ollama",
        model_override: Optional[str] = None
    ) -> LLMResponse:
        """
        Grade a student's answer using LLM.
        
        Args:
            question: The question text
            answer_scheme: Expected answer or marking criteria
            student_answer: Student's answer
            max_marks: Maximum marks for this question
            
        Returns:
            LLMResponse with grading result JSON
        """
        system_prompt = """You are a strict but fair exam grader.

Grading rules:
- Grade ONLY on meaning and required key points from the marking scheme.
- DO NOT deduct marks for spelling, grammar, punctuation, capitalization, or minor missing symbols if the intended meaning/key point is clear.
- Treat common misspellings as correct (e.g., "verity" should count as "verify").
- DO NOT mention spelling/grammar mistakes in feedback.
- You MUST NOT invent content that is not in the student's answer.
- Include 1-2 exact quotes from the student's answer as evidence; each quote maps to one marking point. If none apply, score 0.

Scoring rules:
- The score must be a whole number (no decimals).
- Follow the marking score stated in the marking scheme.
- Score must be within [0, max_marks].
- Decide feedback first, then choose a score that matches it.

Return only valid JSON (no markdown, no extra text):
{"score": <whole number>, "feedback": "<brief justification>", "evidence_quotes": ["<quote 1>", "<quote 2>"]}"""

        q = self._compact_block(question)
        scheme = self._compact_block(answer_scheme)
        ans = self._compact_student_answer(student_answer)

        prompt = f"""Max marks: {max_marks}

Question:
{q}

Marking scheme:
{scheme}

Student answer:
{ans}"""

        provider_norm = (provider or "ollama").strip().lower()
        if provider_norm == "openrouter":
            return await self._call_openrouter(
                prompt, system_prompt, model_override=model_override, request_completion_logprobs=True
            )
        return await self._call_ollama(prompt, system_prompt, request_completion_logprobs=True)
    
    async def check_health(self) -> bool:
        """Check if Ollama is running and model is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name", "") for m in models]
                    return any(self.model in name for name in model_names)
                return False
        except:
            return False


# Singleton instance
llm_service = LLMService()
