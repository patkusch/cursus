"""A model reads the text. Code tests the reading and sends the faults back for another try.

The model is only ever asked for one thing: the JSON reading. Whether that
reading is any good is decided by check.py, not by the model. A reading that
fails goes back with the list of faults, a fixed number of times.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Optional

from pydantic import ValidationError

from cursus.check import Finding, check
from cursus.model import Process, settle
from cursus.prompts import reading_prompt, reading_schema

Ask = Callable[[list[dict]], str]  # the conversation so far -> the model's next reply

OLLAMA = "http://localhost:11434"


class ReadError(RuntimeError):
    pass


def parse_reading(raw: str) -> Process:
    """Models often wrap JSON in a code fence or a sentence, so take the outermost braces."""
    a, b = raw.find("{"), raw.rfind("}")
    if a < 0 or b < a:
        raise ReadError("the answer holds no JSON object")
    try:
        process = Process.model_validate_json(raw[a : b + 1])
    except ValidationError as e:
        faults = "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()[:8])
        raise ReadError(f"the answer does not match the expected layout ({faults})") from e
    return settle(process)


def ollama(model: str, host: str = OLLAMA, *, temperature: float = 0.0, seed: Optional[int] = None, timeout: float = 900) -> Ask:
    """A model served by Ollama on this machine. Nothing leaves the computer."""
    schema = reading_schema()

    def ask(messages: list[dict]) -> str:
        # num_predict stops a model that runs on without closing its JSON; the cut-off answer then fails and is retried
        options: dict = {"temperature": temperature, "num_ctx": 12288, "num_predict": 3000}
        if seed is not None:
            options["seed"] = seed
        payload = {"model": model, "messages": messages, "stream": False, "format": schema, "options": options}
        request = urllib.request.Request(f"{host}/api/chat", data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())["message"]["content"]
        except urllib.error.HTTPError as e:
            raise ReadError(f"Ollama refused the request for '{model}': {e.read().decode('utf-8', 'replace')[:300]}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            raise ReadError(f"could not reach Ollama at {host}: {e}. Is it running?") from e

    return ask


@dataclass
class Reading:
    process: Optional[Process]
    findings: list[Finding] = field(default_factory=list)
    attempts: int = 0
    seconds: float = 0.0
    fault: str = ""  # set when no attempt produced a readable answer

    @property
    def errors(self) -> int:
        return sum(f.level == "error" for f in self.findings)

    @property
    def ok(self) -> bool:
        return self.process is not None and self.errors == 0


def _fix_request(faults: list[str]) -> str:
    listed = "\n".join(f"- {f}" for f in faults)
    return (
        "That reading failed these checks:\n"
        f"{listed}\n\n"
        "Fix every one and answer again with the whole corrected JSON object. "
        "Quotes must be copied word for word from the text. Do not invent steps to make a check pass: "
        "if the text does not say what happens, keep the one exit it states and ask a question about that decision."
    )


def read(text: str, ask: Ask, *, repairs: int = 2, has_answers: bool = False) -> Reading:
    """Ask for a reading of `text`; on faults, ask again up to `repairs` times. Returns the attempt with the fewest errors."""
    began = time.monotonic()
    messages = [{"role": "user", "content": reading_prompt(text, has_answers=has_answers)}]
    best = Reading(process=None)
    for attempt in range(1, repairs + 2):
        reply = ask(messages)
        try:
            process = parse_reading(reply)
        except ReadError as e:
            if best.process is None:
                best = Reading(process=None, attempts=attempt, fault=str(e))
            faults = [str(e)]
        else:
            findings = check(process, text)
            now = Reading(process=process, findings=findings, attempts=attempt)
            if best.process is None or now.errors < best.errors:
                best = now
            if now.errors == 0:
                break
            faults = [f"{f.where}: {f.message}" for f in findings if f.level == "error"]
        # keep the first request and only the latest failed try, so a long text still fits in the model's window
        messages = messages[:1] + [{"role": "assistant", "content": reply}, {"role": "user", "content": _fix_request(faults)}]
    best.attempts = attempt
    best.seconds = time.monotonic() - began
    return best
