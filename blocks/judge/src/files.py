"""judge の graph の place のファイルの名（docs/design/judge-eyes.md の 1.6）。名の字はこのモジュールだけが持つ。標準ライブラリだけ。

- REQUEST: 仕様の段が足した受け入れ条件の行を、依頼の行の後ろに積んだ依頼（spec-in が書く。後の段の request へ）
- PURPOSE_REVIEW: 目的の監査の受けた返答の写し（verdict が書く。independent-design の port purpose_review の形）
- VERDICT: まとめの写し（verdict が書く）
"""
REQUEST = "request.json"
PURPOSE_REVIEW = "purpose-review.json"
VERDICT = "verdict.json"
