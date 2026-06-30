import time
from dataclasses import dataclass

from .config import Settings

# substrings that indicate a TEMPORARY error worth retrying
_TRANSIENT = ("429", "500", "502", "503", "504", "unavailable",
              "resource_exhausted", "overloaded", "timeout", "deadline",
              "temporarily")


def _looks_transient(err: Exception) -> bool:
    s = str(err).lower()
    return any(t in s for t in _TRANSIENT)


@dataclass
class LLMResult:
    text: str
    input_tokens: int
    output_tokens: int
    latency_s: float


class LLMClient:
    def __init__(self, settings: Settings):
        self.s = settings
        self.provider = settings.llm_provider.lower()

        if self.provider == "gemini":
            from google import genai
            self.client = genai.Client(api_key=settings.google_api_key)
        elif self.provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        elif self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=settings.openai_api_key)
        else:
            raise ValueError(f"Unknown llm_provider: {self.provider!r}")

    def _once(self, system: str, user: str, max_tokens: int):
        """One actual call to the chosen provider. Returns (text, in, out)."""
        if self.provider == "gemini":
            from google.genai import types
            r = self.client.models.generate_content(
                model=self.s.llm_model, contents=user,
                config=types.GenerateContentConfig(
                    system_instruction=system, max_output_tokens=max_tokens))
            try:
                text = r.text or ""
            except Exception:
                text = ""
            um = r.usage_metadata
            return (text,
                    getattr(um, "prompt_token_count", 0) or 0,
                    getattr(um, "candidates_token_count", 0) or 0)

        if self.provider == "anthropic":
            r = self.client.messages.create(
                model=self.s.llm_model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}])
            text = "".join(b.text for b in r.content if b.type == "text")
            return text, r.usage.input_tokens, r.usage.output_tokens

        # openai
        r = self.client.chat.completions.create(
            model=self.s.llm_model, max_tokens=max_tokens,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}])
        return (r.choices[0].message.content or "",
                r.usage.prompt_tokens, r.usage.completion_tokens)

    def complete(self, system: str, user: str, max_tokens: int = 400,
                 max_attempts: int = 4) -> LLMResult:
        t0 = time.perf_counter()
        delay = 2.0
        for attempt in range(max_attempts):
            try:
                text, it, ot = self._once(system, user, max_tokens)
                return LLMResult(text, it, ot, time.perf_counter() - t0)
            except Exception as e:
                # retry only temporary errors, and only if attempts remain
                if _looks_transient(e) and attempt < max_attempts - 1:
                    print(f"  (AI busy: {type(e).__name__} — retrying in {delay:.0f}s)")
                    time.sleep(delay)
                    delay *= 2          # 2s, 4s, 8s...
                    continue
                raise
