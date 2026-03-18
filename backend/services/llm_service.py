import httpx
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import sys
import os

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
    
    async def structure_questions(self, text: str) -> LLMResponse:
        """
        Structure extracted text into questions format.
        
        Args:
            text: Extracted text from question paper
            
        Returns:
            LLMResponse with structured questions JSON
        """
        system_prompt = """You are an exam paper analyzer. Extract questions from the text and structure them.
Return a JSON array of questions. Each question should have:
- question_number: The question number (e.g., "1", "1a", "2")
- question_text: The full question text
- question_type: One of "short_answer", "essay", "mcq", "calculation"
- subquestions: Array of subquestions (if any), each with question_number and question_text"""

        prompt = f"""Analyze this exam paper text and extract all questions:

{text}

Return JSON array:
[
  {{
    "question_number": "1",
    "question_text": "...",
    "question_type": "short_answer",
    "subquestions": []
  }}
]"""

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
        student_answer: str,
        max_marks: float
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

Scoring rules:
- The score must be a whole number (no decimals).
- Follow the marking score stated in the answer scheme.
- Score must be within [0, max_marks].

Return only valid JSON (no markdown, no extra text)."""

        q = self._compact_block(question)
        scheme = self._compact_block(answer_scheme)
        ans = self._compact_block(student_answer)

        # Keep the prompt compact but structured for stable grading.
        prompt = (
            "Grade this exam answer.\n"
            f"Max marks: {max_marks}\n\n"
            "Question:\n"
            f"{q}\n\n"
            "Marking scheme:\n"
            f"{scheme}\n\n"
            "Student answer:\n"
            f"{ans}\n\n"
            "Important:\n"
            "- Ignore spelling/grammar/punctuation. If meaning matches a key point, award the mark.\n"
            "- Include 1–2 exact quotes copied from the student's answer as evidence.\n"
            "- If there is no relevant evidence in the student's answer, return score 0.\n\n"
            "Return JSON only:\n"
            f'{{"score": <whole number 0..{max_marks}>, "confidence": <0..1>, "feedback": "<brief justification>", "evidence_quotes": ["<exact quote 1>", "<exact quote 2>"]}}'
        )

        return await self._call_ollama(prompt, system_prompt)
    
    async def batch_grade(
        self,
        questions: List[Dict[str, Any]],
        student_answers: List[Dict[str, Any]]
    ) -> List[LLMResponse]:
        """
        Grade multiple answers (calls grade_answer for each).
        
        Args:
            questions: List of question dicts with question_text, answer_scheme, max_marks
            student_answers: List of answer dicts with question_number, answer_text
            
        Returns:
            List of LLMResponse objects
        """
        results = []
        
        # Create lookup for student answers
        answers_by_num = {a["question_number"]: a["answer_text"] for a in student_answers}
        
        for q in questions:
            q_num = q.get("question_number")
            student_ans = answers_by_num.get(q_num, "")
            
            result = await self.grade_answer(
                question=q.get("question_text", ""),
                answer_scheme=q.get("answer_scheme", ""),
                student_answer=student_ans,
                max_marks=float(q.get("max_marks", 0))
            )
            results.append(result)
        
        return results
    
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
