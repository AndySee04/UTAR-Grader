import httpx
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import OLLAMA_BASE_URL, OLLAMA_MODEL


@dataclass
class LLMResponse:
    """Response from LLM."""
    raw_response: str
    parsed_response: Optional[Dict[str, Any]]
    model_used: str
    processing_time_ms: int
    tokens_used: Optional[int] = None


class LLMService:
    """Service for LLM operations using Ollama."""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model
        self.timeout = 120.0  # 2 minutes timeout for LLM calls
        self.debug = os.getenv("OLLAMA_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}
        self.debug_max_chars = int(os.getenv("OLLAMA_DEBUG_MAX_CHARS", "4000"))
    
    def _dbg(self, label: str, text: str):
        if not self.debug:
            return
        try:
            s = text or ""
            if len(s) > self.debug_max_chars:
                s = s[: self.debug_max_chars] + "\n... [truncated] ..."
            print(f"\n[OLLAMA DEBUG] {label}\n{s}\n")
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

    def _annotate_scheme_with_keypoint_marks(self, scheme: str, keypoint_marks: str) -> str:
        """Append `| <marks>` to each keypoint line for explicit scoring cues."""
        s = self._compact_block(scheme)
        mark = (keypoint_marks or "").strip() or "1"
        if not s:
            return ""

        annotated = []
        for raw_line in s.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if "|" in line:
                annotated.append(line)
                continue
            if line.startswith(("-", "*")) or re.match(r"^\d+[\).\s]", line):
                annotated.append(f"{line} | {mark}")
            else:
                annotated.append(f"- {line} | {mark}")
        return "\n".join(annotated)
    
    async def _call_ollama(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
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
        
        if self.debug:
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
            response.raise_for_status()
            result = response.json()
        
        processing_time = int((time.time() - start_time) * 1000)
        raw_response = result.get("message", {}).get("content", "")
        
        if self.debug:
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
        
        return LLMResponse(
            raw_response=raw_response,
            parsed_response=parsed,
            model_used=self.model,
            processing_time_ms=processing_time,
            tokens_used=result.get("eval_count")
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
        system_prompt = """You are a text correction assistant. Your job is to fix OCR errors in exam papers.
Fix obvious spelling mistakes, correct character misrecognitions (like 'l' vs '1', 'O' vs '0'), 
and improve formatting. Keep the original meaning and structure intact.
Return ONLY the corrected text, no explanations."""

        prompt = f"""Please correct this OCR text from an exam paper:

{raw_text}

Return the corrected text:"""

        return await self._call_ollama(prompt, system_prompt)
    
    async def generate_marking_guide(
        self,
        question_text: str,
        answer_scheme_text: str
    ) -> LLMResponse:
        """
        Generate marking guide from question paper and answer scheme.
        
        Args:
            question_text: Text from question paper
            answer_scheme_text: Text from answer scheme
            
        Returns:
            LLMResponse with marking guide JSON
        """
        system_prompt = """You are an exam marking guide generator. Create a structured marking guide 
based on the question paper and answer scheme provided.
Return a JSON array where each item represents a question with its marking criteria."""

        prompt = f"""Create a marking guide from:

QUESTION PAPER:
{question_text}

ANSWER SCHEME:
{answer_scheme_text}

Return JSON array:
[
  {{
    "question_number": "1",
    "question_text": "the question",
    "question_type": "short_answer|essay|mcq|calculation",
    "answer_scheme": "expected answer or marking criteria",
    "max_marks": 5
  }}
]"""

        return await self._call_ollama(prompt, system_prompt)
    
    async def grade_answer(
        self,
        question: str,
        answer_scheme: str,
        keypoint_marks: str,
        student_answer: str,
        max_marks: float
    ) -> LLMResponse:
        """
        Grade a student's answer using LLM.
        
        Args:
            question: The question text
            answer_scheme: Expected answer or marking criteria
            keypoint_marks: Per-keypoint mark allocation guidance
            student_answer: Student's answer
            max_marks: Maximum marks for this question
            
        Returns:
            LLMResponse with grading result JSON
        """
        system_prompt = """You are a strict exam grader.

Rules:
- Grade based only on the marking scheme.
- Ignore spelling/grammar if meaning is clear.
- Ignore punctuation/spacing/line breaks if meaning is clear.
- Ignore incorrectsymbol/formating if meaning is clear.
- Do not infer or add missing points.

Scoring:
- Each correct keypoint uses the provided marks per keypoint.
- Total score must be an integer within [0, max_marks].

Output:
Return valid JSON only:
{"score": int, "feedback": string, "evidence_quotes": string[]}"""

        q = self._compact_block(question)
        scheme = self._compact_block(answer_scheme)
        keypoints = self._compact_block(keypoint_marks)
        ans = self._compact_student_answer(student_answer)
        scheme_with_marks = self._annotate_scheme_with_keypoint_marks(scheme, keypoints)

        prompt = (
            "Question:\n"
            f"{q}\n\n"
            "Answer guide:\n"
            f"- max_marks: {max_marks}\n"
            f"- marks_per_keypoint: {keypoints or '1'}\n"
            f"- marking_scheme:\n{scheme_with_marks or scheme}\n\n"
            "Student answer:\n"
            f"{ans}\n\n"
            "Instructions:\n"
            "- Ignore grammar/spelling/punctuation issues.\n"
            "- Match student answers to marking scheme by meaning.\n"
            "- Each quote must support one keypoint.\n"
            "- Return score as an integer within [0, max_marks].\n\n"
            "Return JSON only.\n"
            '{"score": int, "feedback": string, "evidence_quotes": string[]}'
        )

        return await self._call_ollama(prompt, system_prompt)
    
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
