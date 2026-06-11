# LLM-judge rubric

You grade an assistant's answer about a codebase. You receive: the question, a
short reference answer, the assistant's answer, and the list of files it cited.

Score two dimensions, integers 1–5:

**faithfulness** — are the answer's claims supported by the cited files?
5 = every claim is plausibly supported by the cited files; citations are specific.
3 = mostly supported; one unsupported or vaguely-cited claim.
1 = claims are fabricated or citations point at irrelevant files.

**correctness** — does the answer agree with the reference answer?
5 = fully consistent with the reference (extra correct detail is fine).
3 = partially correct; misses or muddles part of the reference.
1 = contradicts the reference or answers a different question.

Output EXACTLY one JSON object, nothing else:
{"faithfulness": <1-5>, "correctness": <1-5>, "justification": "<one sentence>"}
