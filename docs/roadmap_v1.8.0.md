[v1.8] Plugin Expansion

Goal:
plugin / hook の責務境界を整理し、
「拡張できるフレームワーク」として分かりやすく使える状態にする。
builtin plugin・sample plugin・plugin docs を通して、
plugin authoring の入口を明確化する。

---

[Day1] Plugin Contract Review

- plugins/base.py の contract を見直す
- BasePlugin の責務を明確化する
- setup / on_start / on_stop の位置づけを整理する
- hook 登録は setup で行う方針を明文化する
- plugin 側が runtime に期待してよい範囲を整理する

Goal:
plugin 実装者が従うべき最小 contract を明確にする

---

[Day2] Plugin Manager Cleanup

- plugins/manager.py の load / setup / start / stop 流れを整理する
- builtin plugin 読み込み経路を見直す
- plugin 単位のエラーハンドリングを分かりやすくする
- plugin manager の責務を「管理」に寄せる
- 現行 builtin plugin が問題なく動くことを確認する

Goal:
plugin manager の挙動が読みやすく、一貫した状態にする

---

[Day3] Hook / Event Contract Cleanup

- core/events.py の責務を整理する
- 現行 hook 名と使い方を見直す
- plugin author が使うイベント面を分かりやすくする
- emit の期待値を整理する
- runtime / pipeline / plugin 間のイベント境界を明確化する

Goal:
plugin がどのイベントを使って拡張するのか分かりやすい状態にする

---

[Day4] Builtin Plugin Expansion

- ConsoleLoggerPlugin を軽く強化する
- EmotionVTSPlugin の役割を再確認する
- sample / reference として使える builtin plugin を追加する
- 実用性より「plugin の書き方の見本」を優先する
- plugin 増加後も runtime flow が崩れないことを確認する

Goal:
builtin plugin を通して、拡張イメージが伝わる状態にする

---

[Day5] Sample Plugin / Example Flow

- 最小 sample plugin を追加する
- plugin の配置場所と有効化方法を実例で示す
- hook 登録の最小パターンをサンプル化する
- runtime とのやり取り例を分かりやすくする
- plugin author が真似しやすい最小構成を作る

Goal:
「自分でも plugin を書けそう」と感じられる入口を作る

---

[Day6] Plugin Docs

- plugin 作成方法のドキュメントを追加する
- lifecycle の説明を整理する
- hook / event の使い方を説明する
- runtime との関係を説明する
- sample plugin の読み方と使い方を案内する

Goal:
plugin authoring の導線を README / docs 上で分かりやすくする

---

[Day7] Cleanup & Consistency Pass

- plugin 関連ファイル全体の cleanup を行う
- touched files ベースでコメント / docstring を補強する
- builtin plugin / sample plugin / docs / README の整合性を確認する
- preset 動作への影響がないことを確認する
- v1.8.0 リリース前提の最終整理を行う

Goal:
plugin 拡張基盤が一貫した状態で v1.8 を締める

---

[Design Notes]

- v1.8 は plugin を「増やすこと」より
  「plugin の使い方が分かること」を重視する
- plugin lifecycle は setup / on_start / on_stop を基本とする
- hook 登録は setup で行う方針を維持する
- runtime は event を emit し、plugin はそれを購読する構成を主軸にする
- plugin manager に処理責務を寄せすぎず、管理責務に留める
- builtin plugin は実用機能より reference 実装としての分かりやすさを優先する
- 大規模な plugin discovery / dependency 解決は v1.8 のスコープ外とする

---

[Expected Outcome]

- plugin contract が分かりやすい
- plugin manager の流れが読みやすい
- builtin plugin が reference として機能する
- sample plugin を見れば最小実装が分かる
- plugin docs から拡張の入口に入れる
- 「拡張できるフレームワーク」としての見え方が強くなる