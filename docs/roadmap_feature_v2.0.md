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

Goal:
AIキャラクターの表情制御がFramework構成で扱える状態になる

---

[v1.6] Multi-LLM Base & Practical Presets

- LLM provider 抽象化（interface 設計）
- OpenAI provider 追加
- Claude provider 追加
- Gemini provider 整理
- llm/ ディレクトリ構成整理
- preset に LLM 設定を持たせる
  - llm_provider
  - llm_model
- APIキー管理整理（env）
- provider切替がpresetで可能になる
- エラーメッセージ改善（未設定キーなど）
- presets の拡充
  - text_chat_openai
  - text_chat_claude
  - text_vts
  - voice_vts
  - bilingual系
- plugin 経由で外部APIを叩ける構造整理
- STT / TTS の構造整理（将来のcloud対応を見据える）

[Note]
v1.5開発時点の既知課題:
`voice_vts` では、STT入力待ちとキーボード入力待ちを同時に走らせる構造が一部不安定。
主因はTTS再生そのものではなく、`stt.listen()` とキーボード入力タスクの並列待機 / cleanup 周りにある可能性が高い。
この点は v1.6 の STT / TTS 構造整理で再確認・再設計する。

[Performance]
- 入力〜応答〜音声出力の処理時間を計測
- ボトルネックの可視化
- 初回レスポンスの待ち時間短縮
- 不要な同期処理の整理

Goal:
複数LLMをpresetで切り替えられ、実用的なプリセットが揃う

---

[v1.7] UX & Streaming

- LLMストリーミング応答対応
- TTS逐次再生（ストリーム再生）
- 途中表示 / typing表現
- 音声会話の体感レスポンス改善
- エラーメッセージ・ログの改善
- 初回セットアップ導線改善

Goal:
「速くて使いやすい」と感じる体験になる

---

[v1.8] Plugin Expansion

- plugin APIの安定化
- plugin manager の拡張
- builtin plugin の追加
  - console logger 強化
  - simple memory
  - external API sample
- pluginのサンプル充実
- ドキュメント整備（plugin作成方法）

Goal:
「拡張できるフレームワーク」として成立する

---

[v1.9] Stabilization

- 軽いテスト整備
- preset / plugin の動作確認
- 互換性チェック
- 不要ログ削減
- エッジケース修正
- サンプルプロジェクト追加

Goal:
安定して配布できる状態にする

---

[v2.0] Framework Release

- ドキュメント全面整備
- Quick Start 完成
- サンプル構成の洗練
- 初心者でも使える導線確立
- リポジトリ構成の最終整理

Goal:
「フレームワークとして完成」と言える状態

---

[Design Principles]

- 構造 → 抽象化 → UX → 拡張 → 安定 の順で進める
- 1日1責務・壊さず終える
- preset / character / plugin を中心に拡張する
- loader は「読むだけ」、処理ロジックを持たせない
- runtime に責務を集約する

---

[Future Ideas (Optional)]

- 自動LLM fallback
- キャッシュ機構
- 非同期パイプライン最適化
- Web UI / 設定画面
- クラウド設定保存
- マルチセッション対応
