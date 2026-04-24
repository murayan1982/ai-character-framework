[Goal]

開発者向けAIフレームワーク
音声会話 + Live2D の体験基盤
構成（preset / character / plugin / LLM）で挙動を切り替えられる設計

---

[v1.4] Config Foundation

- config/loader.py の完成
- RuntimeConfig 導入
- env → preset → character → default の優先順位確立
- presets 読み込み対応
- character 読み込み対応
- input / output language 分離
- runtime に config 注入
- 最小 plugin 基盤作成
- 起動時に設定表示
- run scripts 整備
- README 最低限整備

Goal:
設定ベースで動作が切り替わる「土台」が完成する

---

[v1.5] Emotion / VTS Expression Control

- LLM応答にemotion tagを付与
- emotion tagを本文から分離
- 表示 / TTS用テキストからemotion tagを除去
- characterごとのVTS hotkey mapping
- VTS hotkey trigger
- plugin経由でemotion処理を拡張可能にする
- VTS未接続 / hotkey未設定でも会話を継続
- RuntimeConfig を main runtime flow の正本として扱う方針を明確化
- character-level hotkey mapping によって Framework abstraction と model-specific hotkey を分離
- runtime直結MVPで emotion / VTS 経路を成立させる
- legacy path（change_expression / VTS_EMOTION_ALIAS / old global flags）を明示
- settings.py / models.py の責務再配分方針を整理する

Goal:
AIキャラクターの表情制御がFramework構成で扱え、
主経路と legacy path の境界が明確になった状態にする

---

[v1.6] Config Responsibility Cleanup & Framework Readability

- settings.py / models.py の責務再配分
- LLM registry を settings.py から分離
- TTS registry を models.py から分離
- secrets / developer defaults / legacy compatibility の責務を切り分ける
- RuntimeConfig を runtime behavior の source of truth とする構成へ寄せる
- preset / character / runtime / registry の責務境界を整理する
- loader / runtime flow の可読性を改善する
- preset の役割を整理し、`text_chat` を safe default として明確化する
- default preset を廃止し、起動導線を `text_chat` 基準に揃える
- plugin / hook contract を整理する
- developer configuration guide を追加する
- plugin / hook contract documentation を追加する
- cleanup / consistency pass を行う
- config cleanup 後の preset 動作確認を行う
  - text_chat
  - text_vts
  - voice_vts
  - bilingual_ja_en

[Note]
v1.5 開発時点から継続している既知の観測事項:
`voice_vts` では、環境やタイミングにより VTS / TTS 経路に軽い不安定さが見えることがある。
v1.6 では config / responsibility cleanup を優先し、
音声経路の本格的な安定化や再設計は今後の課題として扱う。

Goal:
設定責務の境界が明確で、
RuntimeConfig / preset / character / registry を中心に読みやすく拡張しやすい
Framework 構成へ整理された状態にする

---

[v1.7] Streaming Foundation

- LLM逐次応答の表示基盤を整理する
- chunk表示と本文表示の責務を整理する
- emotion tag を含む逐次出力の扱いを整理する
- text系 preset の streaming 表示基盤を整える
- voice系で流用しやすい出力経路を整理する

Goal:
streaming 表示を扱うための基盤が明確で、
text / voice 両方へ発展しやすい状態にする

---

[v1.8] Plugin & Runtime Extensibility

- plugin APIの安定化
- plugin manager の拡張
- builtin plugin の追加
  - console logger 強化
  - simple memory
  - external API sample
- plugin sample の整理
- plugin / hook contract documentation の補強
- runtime との接続点を整理する

Goal:
「拡張できる runtime / plugin framework」として成立する

---

[v1.9] Streaming UX & Developer Guidance Polish

- streaming 表示体験の改善
- `voice_vts` の text fallback と shutdown flow の整理
- STT待機 / TTS再生 / 終了体験の軽い polish
- preset の役割と first run 導線の整理
- character customization 入口の整理
- README / docs / distribution wording の更新
- repository naming の整理
- cleanup / consistency pass

Goal:
起動してから使い方が分かり、
text / voice / preset / character の導線が自然に伝わる状態にする

---

[v1.10] Character Structure & Developer Flow Cleanup

- character loader の責務を整理する
- `profile / system / vts_hotkeys` の役割をより明確化する
- character 追加 / 差し替えの流れを整理する
- character naming / file naming の整合性を確認する
- 1 character = 1 directory 運用を前提に読みやすさを高める
- character customization guide を補強する
- developer flow の小さな cleanup を行う

Goal:
character 周りの構造と編集導線がより分かりやすく、
開発者が差し替え / 追加しやすい状態にする

---

[v2.0] Minimum AI Character Conversation UX

- text / Live2D / voice presets を前提に、最低限の会話体験を確認する
- user input → LLM response → display / TTS / emotion / VTS の流れを整理する
- 会話状態の見え方を確認する
  - waiting
  - listening
  - thinking
  - speaking
  - exiting
- `text_chat` / `text_vts` / `voice_vts` の体験差分を整理する
- character prompt / emotion / VTS expression のつながりを確認する
- 音声会話の自然な待機 / 応答 / 発話フローについて、最低限の方針を README / docs に反映する
- v2.0 時点で対応する範囲と、v2.0 以降に残す課題を明確にする
- Quick Start / README / docs を v2.0 方針に合わせて更新する

[Out of Scope for v2.0]

The following topics are intentionally left outside the v2.0 scope.
Some of them are tracked in `roadmap_feature_v3.0.md`.

- STT / TTS provider abstraction の本格実装
- latency 改善の本格対応
- interrupt / barge-in の本格実装
- multi-character conversation の本格実装
- audio pipeline の大規模再設計
- Web UI / 設定画面

Goal:
text / Live2D / voice を通した AIキャラクター会話体験として、
最低限の待機・応答・発話・表情連携の流れが説明でき、
v2.0 以降の音声基盤改善や会話UX拡張へ無理なく進める状態にする

---

[Design Principles]

- 構造 → 抽象化 → UX → 拡張 → 安定 の順で進める
- 1日1責務・壊さず終える
- preset / character / plugin を中心に拡張する
- loader は「読むだけ」、処理ロジックを持たせない
- runtime に責務を集約する
- RuntimeConfig を runtime behavior の source of truth とする
- settings.py は最終的に神ファイル化させない
- provider/model registry は runtime config から分離する
- legacy compatibility は main framework flow から分けて管理する
- v1.x では開発者がすぐ試せる土台づくりを優先する
- 会話デザインとしてのUX向上は v2.0 以降のテーマとして扱う
- character は「誰として振る舞うか」、preset / runtime は「どう動くか」として整理する

---

[Future Ideas (Optional)]

These are broader future ideas that are not part of the v2.0 scope
and are not yet assigned to a specific milestone.

- Settings / config cache for faster startup or runtime switching
- Advanced LLM fallback / routing
- Cloud-based preset / character settings
- Multi-session runtime support

[Cache Note]

Caching should be considered carefully for conversation UX and framework responsibility.

Settings / config caching may help improve startup or runtime responsiveness
without directly affecting conversation variety.

TTS caching is intentionally not treated as a core framework feature for now.
It may create high maintenance cost around provider differences, cache keys,
storage management, licensing concerns, and repetitive conversation patterns.

If TTS caching is explored in the future, it should likely be handled as an
optional plugin or provider-specific extension rather than core runtime behavior.