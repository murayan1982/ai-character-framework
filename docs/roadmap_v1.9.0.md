[v1.9] Streaming UX & Character/Preset Polish

Goal:
Streaming UX と Character / Preset の導線を整理し、
「起動してから使い方が分かる」「実行中の体験が自然」
と感じられる状態にする。

v1.9 では音声系を主テーマにはせず、
終了体験・再生待機・ログ表示など、
UX に直結する最小限の polish のみに留める。

---

[Day1] Streaming UX Review

- 現在の応答表示フローを整理する
- AI 出力開始タイミングの責務を確認する
- text_chat / text_vts / voice_vts の見え方の差を確認する
- 空応答や短い応答時の見え方を見直す
- 改善対象を「表示」「待機」「中断」に分けて整理する

Goal:
現在の streaming 体験のどこを整えるべきかを明確にする

---

[Day2] Streaming Output Cleanup

- chunk 表示の流れを整理する
- 「AI: ...」と実応答表示のつながりを見直す
- 応答開始時の console UX を自然にする
- 空 chunk / 断片的な chunk の扱いを整理する
- text 系 preset での表示体験を安定させる

Goal:
text 系の streaming 表示を読みやすく自然な状態にする

---

[Day3] Playback / Interrupt UX Cleanup

- TTS 再生待機まわりの責務を整理する
- Ctrl+C / exit / 通常終了時の見え方を軽く polish する
- voice 実行時の不要ログや過剰なノイズを見直す
- STT 待機 / TTS 再生 / 終了のつながりを自然にする
- 音声系は大改修せず、UX に効く範囲だけ触る

Goal:
voice_vts 実行時の体験を荒さの少ない状態にする

---

[Day4] Preset Flow Review

- APP_PRESET → presets/*.json → runtime の流れを整理する
- preset ごとの責務を見直す
- text_chat を safe default として分かりやすくする
- preset 名と実挙動の対応を確認する
- 初回起動時に迷いにくい preset 導線を整える

Goal:
preset の役割と選び方が分かりやすい状態にする

---

[Day5] Character Flow Cleanup

- characters/* の責務を整理する
- profile / system / hotkeys の役割を明確化する
- character 差し替え時にどこを見ればよいか分かるようにする
- character ごとの差分点を README / docs で説明しやすくする
- runtime / character 境界を読みやすくする

Goal:
character customization の入口が分かりやすい状態にする

---

[Day6] Docs / README Polish

- streaming UX の説明を必要な範囲で更新する
- preset / character の導線を README で整理する
- first run の案内をより分かりやすくする
- よく触る設定ファイルと変更ポイントを整理する
- v1.9 時点の使い方が README / docs から自然に伝わるようにする

Goal:
README / docs を見れば起動・変更・確認の流れが分かる状態にする

---

[Day7] Cleanup & Consistency Pass

- touched files ベースでコメント / docstring を補強する
- streaming / preset / character / docs / README の整合性を確認する
- text_chat / text_vts / voice_vts の軽い確認を行う
- 一時確認コードや不要ログが残っていないか確認する
- v1.9.0 リリース前提の最終整理を行う

Goal:
v1.9 の体験改善が一貫した状態でリリースできるようにする

---

[Scope Notes]

- v1.9 の主軸は Streaming UX と Character / Preset UX とする
- 音声系は UX に直結する最小限の polish のみに留める
- STT / TTS の基盤再設計や provider abstraction の大整理は v2.0 以降とする
- latency 改善や音声パイプライン再設計は v2.0 以降の課題として残す
- text_chat を safe default とする方針は維持する
- 初回起動から preset / character 理解までの導線改善を重視する

---

[Expected Outcome]

- streaming 表示が自然で読みやすい
- voice 実行時の終了体験とログ表示が荒れにくい
- preset の役割と選び方が分かりやすい
- character customization の入口が見つけやすい
- README / docs から使い方と変更点を追いやすい
- v2.0 に向けて音声基盤の大課題を無理なく残せる
