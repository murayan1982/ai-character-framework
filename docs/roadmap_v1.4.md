[Goal]

Preset system
Character system
Plugin system
Input/Output language separation

[Concept]

開発者向けフレームワーク（アプリではない）
音声会話 + Live2D 体験の基盤
構成で挙動を切り替えられる設計

[Core Features]

presetで起動モード切替
characterでsystem prompt切替
pluginで拡張可能
入力言語 / 出力言語を分離

[Config Design]

RuntimeConfig導入
input_language_code
output_language_code
env > preset > character > default の優先順位

[Structure Plan]

config/loader.py
presets/
characters/
plugins/
core/runtime.py
scripts/

[v1.4 Must]

config loader追加
preset json追加
character profile/system追加
runtimeへconfig注入
input/output language分離
最小plugin基盤
run batch追加
README更新

[Daily Plan]
Day 1

config/loader.py を作る
RuntimeConfig を定義する
input_language_code / output_language_code を含める
envから最小構成を読めるようにする
scripts/run_text_chat.bat を追加する
終了条件: load_runtime_config() が返る / batでmain.pyが起動する

Day 2

presets/default.json を作る
presets/text_chat.json を作る
loaderでpreset jsonを読めるようにする
終了条件: APP_PRESETでconfig内容が変わる

Day 3

characters/default/profile.json を作る
characters/default/system.txt を作る
loaderでcharacter profileとsystem promptを読めるようにする
終了条件: config.system_prompt が埋まる

Day 4

main.py から load_runtime_config() を呼ぶ
initialize_components(config) の呼び出し準備をする
終了条件: main.py から config が見える

Day 5

core/runtime.py を initialize_components(config) 化する
runtime["config"] を持たせる
起動時に preset / character / input_language / output_language を表示する
終了条件: 起動が壊れない / 設定表示が出る

Day 6

feature flag を configベースに寄せる
input voice / output voice / vts の切替を configで反映する
TTS provider（none / local / elevenlabs）をpresetで制御する
終了条件: presetでfeatureのON/OFFおよびTTS providerが切り替わる

Day 7

STT に input_language_code を渡す
TTS に output_language_code を渡す
終了条件: 入出力の言語設定が別々に通る

Day 8

LLM の応答言語指示を runtime側で追加する
system promptに output language 指示を足す
終了条件: 入力日本語 / 出力英語みたいな構成の土台が動く

Day 9

presets/text_vts.json を作る
presets/voice_vts.json を作る
bilingual系 preset も1つ作る
（余裕があれば TTS provider違いのpresetも検討）
終了条件: 主要presetが揃う

Day 10

plugins/base.py を作る
plugins/manager.py を作る
終了条件: plugin manager をimportできる

Day 11

plugins/builtin/console_logger.py を作る
runtime初期化時にpluginをロードする
終了条件: plugin経由でログが出る

Day 12

scripts/run_text_vts.bat を作る
scripts/run_voice_vts.bat を作る
終了条件: 主要presetをbatで起動できる

Day 13

READMEにQuick Startを追加する
preset / character / language settings / plugin の最低限説明を書く
終了条件: 初見で使い始められる

Day 14

全presetの軽い動作確認
不要ログ整理
小さい不具合修正
終了条件: v1.4.0として一区切りつけられる

[Operating Rules]

1日1時間
1日1責務まで
壊さず終える
1日1コミット
詰まったら plugin や補助preset を後回しにする

[Current Status]

設計整理済み
Day 1 から着手可能