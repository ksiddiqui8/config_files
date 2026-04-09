from pathlib import Path

NOTEBOOK_FILE = Path.home() / ".local/share/qtile_dashboard/shared_notebook.md"


def extract_user_content(text):
    if "## LLM SUMMARY" in text:
        return text.split("## LLM SUMMARY")[0].strip()
    return text


def write_summary(original_text, summary):
    if "## LLM SUMMARY" in original_text:
        before = original_text.split("## LLM SUMMARY")[0].rstrip()
        return f"{before}\n\n## LLM SUMMARY\n\n{summary}\n"
    else:
        return f"{original_text}\n\n## LLM SUMMARY\n\n{summary}\n"


def fake_llm_summary(text):
    # Placeholder (we’ll replace this with real LLM soon)
    lines = text.splitlines()
    lines = [l for l in lines if l.strip()]

    if not lines:
        return "Nothing to summarize."

    return "Hello from LLM"


def main():
    
    print("SCRIPT STARTED")

    print("Using file:", NOTEBOOK_FILE)

    text = NOTEBOOK_FILE.read_text(encoding="utf-8")

    user_content = extract_user_content(text)
    summary = fake_llm_summary(user_content)

    new_text = write_summary(text, summary)
    NOTEBOOK_FILE.write_text(new_text, encoding="utf-8")


if __name__ == "__main__":
    main()
