"""Applies the required fixes to the AI/ML 3 files already copied into app/core.
Run from the repo root:  python patch_aiml3.py
Safe to run twice (it skips edits that are already done)."""
import re
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
core = root / "app" / "core"
INTENTS = ["conversation_ideas", "help_me_understand", "next_steps", "privacy_safety"]
done = []


def read(p):
    return p.read_text(encoding="utf-8")


def write(p, text):
    p.write_text(text, encoding="utf-8", newline="\n")


# 1) pipeline.py: remove the sys.path hack, make prompt paths independent of the working folder
p = core / "pipeline.py"
s = read(p)
before = s
s = re.sub(r"# Add project root to Python path\s*sys\.path\.append\(\s*os\.path\.dirname\(\s*"
           r"os\.path\.dirname\(\s*os\.path\.abspath\(__file__\)\s*\)\s*\)\s*\)\s*", "", s)
s = re.sub(r"^import sys[ \t]*\n", "", s, flags=re.M)
s = re.sub(r"^import os[ \t]*\n", "", s, flags=re.M)
if "PROMPTS_DIR" not in s:
    block = ('PROMPTS_DIR = Path(__file__).parent / "prompts"\n\n'
             "PROMPT_FILES = {\n"
             + "".join(f'    "{i}": PROMPTS_DIR / "{i}.txt",\n' for i in INTENTS)
             + "}")
    s, n = re.subn(r"PROMPT_FILES = \{.*?\n\}", lambda m: block, s, count=1, flags=re.S)
    if n != 1:
        sys.exit("ERROR: could not find PROMPT_FILES in pipeline.py - edit it by hand")
    s = s.replace("import json\n", "import json\nfrom pathlib import Path\n", 1)
if s != before:
    write(p, s)
    done.append("pipeline.py: removed sys.path hack, prompt paths now relative to the file")

# 2) llm_provider.py: import google-genai lazily
p = core / "llm_provider.py"
s = read(p)
before = s
s = re.sub(r"^from google import genai[ \t]*\n", "", s, count=1, flags=re.M)
if not re.search(r"^[ \t]+from google import genai", s, flags=re.M):
    s, n = re.subn(r"^([ \t]*)self\.client = genai\.Client\(",
                   lambda m: f"{m.group(1)}from google import genai\n\n{m.group(1)}self.client = genai.Client(",
                   s, count=1, flags=re.M)
    if n != 1:
        sys.exit("ERROR: could not find 'self.client = genai.Client(' in llm_provider.py - edit it by hand")
if s != before:
    write(p, s)
    done.append("llm_provider.py: google-genai now imported inside GeminiLLMProvider.__init__")

# 3) prompts: ask for JSON output
for i in INTENTS:
    p = core / "prompts" / f"{i}.txt"
    s = read(p)
    if "Respond ONLY with valid JSON" not in s:
        s = s.rstrip() + (
            "\n\nOutput format:\nRespond ONLY with valid JSON and nothing else, in exactly this shape:\n"
            f'{{"intent": "{i}", "response": ["item 1", "item 2"]}}\n')
        write(p, s)
        done.append(f"prompts/{i}.txt: JSON output instruction added")

# 4) requirements.txt: pin google-genai
p = root / "requirements.txt"
s = read(p)
if "google-genai" not in s:
    write(p, s.rstrip() + "\ngoogle-genai==2.29.0\n")
    done.append("requirements.txt: google-genai==2.29.0 added")

print("\n".join(done) if done else "Nothing to change (already patched).")
