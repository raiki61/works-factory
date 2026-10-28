"""theme の block の試験が使う値（対象の小さなリポジトリ・テーマの md・受け付けを全部通る設計の案）"""
AGENTS_MD = "# Rules\n\nNew review viewpoints are blocks.\nEach block runs on its own.\n"
RULES_MD = "# Review rules\n\n1. Read the diff.\n2. Name the line.\n\n3. Keep the old wording.\n"   # 6 行（2・5 行は空）
THEME_MD = "# Theme\n\nShould the review rules be split into one block per rule?\n\nThe owner wants each rule callable on its own.\n"


def reply() -> dict:
    """受け付けを全部通る設計の案（人の答え H1 を使い、docs/rules.md を作り変える）"""
    return {
        "question": "Should the review rules be split into one block per rule?",
        "purpose": "Make each review rule callable on its own.",
        "premises": [{"id": "P1", "what": "Each rule must be callable on its own.", "by": "owner", "from": "theme:5"},
                     {"id": "P2", "what": "The owner prefers short files.", "by": "owner", "from": "H1"},
                     {"id": "P3", "what": "The rules file has no other reader.", "by": "assumed", "from": "No reference was found."}],
        "current": [{"id": "N1", "what": "The rule that viewpoints are blocks.", "where": "AGENTS.md:3"},
                    {"id": "N2", "what": "The review rules in one file.", "where": "docs/rules.md:1-6"}],
        "parts": [{"id": "D1", "what": "One block per rule.", "where": "workflows/<rule>/", "why": "AGENTS.md:3 asks for blocks."}],
        "reuse": [{"part": "D1", "existing": ["N1", "N2"], "enough": False, "why_not": "The file cannot be called per rule."}],
        "checks": [{"rule": "AGENTS.md:4", "answer": "Each block runs on its own.", "where": "D1"}],
        "asks": [{"id": "Q1", "ask": "Should the old file stay as an index?", "pick": "A1", "pick_why": "Readers keep one entry.",
                  "options": [{"id": "A1", "what": "Keep it as an index.", "cost": "One more file to keep.", "gain": "One entry for readers."},
                              {"id": "A2", "what": "Remove it.", "cost": "Readers lose the entry.", "gain": "Nothing to keep in sync."}]}],
        "decided": [{"id": "R1", "what": "Each rule becomes a block.", "by": "AGENTS.md:3", "why": "The rule settles it."}],
        "changes": [{"id": "C1", "where": "docs/rules.md", "what": "Split the rules into blocks.", "op": "rework", "parts": ["D1"]}],
        "inventory": [{"path": "docs/rules.md", "lines": "1-1", "gist": "The heading.", "to": "keep", "dest": "", "why": ""},
                      {"path": "docs/rules.md", "lines": "3-4", "gist": "Rules 1 and 2.", "to": "move", "dest": "D1", "why": ""},
                      {"path": "docs/rules.md", "lines": "6-6", "gist": "Rule 3.", "to": "drop", "dest": "",
                       "why": "The block keeps its own wording."}],
        "narrows": [{"what": "docs/rules.md:6-6 is dropped.", "decided_by": "H1"}],
        "block_answers": [],
        "answers_used": [{"answer": "H1", "applied": ["P2"]}],
    }


ANSWERS = [{"id": "H1", "kind": "owner_words", "text": "Short files are easier to read."}]
