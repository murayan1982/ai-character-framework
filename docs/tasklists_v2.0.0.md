[v2.0 Day Plan]

[Day1] Scope & Conversation UX Review

- v2.0 で扱う会話UXの範囲を整理する
- v2.0 で扱わない音声基盤改善を明確にする
- text / Live2D / voice の最小体験を定義する
- 既存 README / roadmap とスコープのズレを確認する

Goal:
v2.0 の着地点と out-of-scope が明確になった状態にする

---

[Day2] Conversation Flow Review

- user input → LLM response → display / TTS / emotion / VTS の流れを確認する
- text_chat / text_vts / voice_vts の会話フロー差分を整理する
- session / pipeline / runtime の責務を確認する
- 会話中の状態遷移が読みやすいか確認する

Goal:
会話フロー全体が v2.0 の最小UXとして説明できる状態にする

---

[Day3] Runtime State & User Feedback Cleanup

- waiting / listening / thinking / speaking / exiting の見え方を確認する
- console 表示やログが会話状態を邪魔していないか確認する
- text / voice fallback / shutdown flow の見え方を整理する
- 必要なら小さな表示改善を行う

Goal:
ユーザーが今システムが何をしているか分かりやすい状態にする

---

[Day4] Emotion / VTS Conversation Consistency

- emotion tag → clean text → TTS → VTS hotkey の流れを確認する
- emotion が表示文 / 音声出力に混ざらないことを確認する
- VTS 未接続 / hotkey 未設定時の fallback を確認する
- character-level VTS mapping の説明と実装の整合性を確認する

Goal:
会話・音声・表情の連携が最低限一貫している状態にする

---

[Day5] Preset Experience Check

- text_chat の最小会話体験を確認する
- text_vts の Live2D 付き体験を確認する
- voice_vts の音声会話体験を確認する
- bilingual_ja_en の language separation を確認する
- preset ごとの目的が README と一致しているか確認する

Goal:
各 preset の体験差分が分かりやすく、README と実動作が揃っている状態にする

---

[Day6] README / Docs v2.0 Alignment

- Quick Start / First Run / Presets / Character Customization / Runtime Configuration を確認する
- v2.0 時点の会話UX方針を README に反映する
- 既知の制限と今後の課題を整理する
- v2.0 以降に残す voice foundation / latency / provider abstraction を明記する

Goal:
README / docs が v2.0 の着地点を正しく説明している状態にする

---

[Day7] Final Consistency Pass

- touched files の comment / docstring を確認する
- README / roadmap / implementation の整合性を確認する
- text_chat / text_vts / voice_vts / bilingual_ja_en の軽い確認を行う
- 不要ログ・一時確認コード・古い説明が残っていないか確認する
- v2.0.0 リリース前提の最終整理を行う

Goal:
AIキャラクター会話体験として v2.0.0 を一区切りでリリースできる状態にする