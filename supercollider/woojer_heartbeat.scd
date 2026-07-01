/*
woojer_heartbeat.scd  v3
------------------------
Woojer Strap Edge 用 偽心拍振動パッチ

アーキテクチャ:
  HW706 → woojer_controller.py --[/heartbeat/bpm raw_bpm]--> SC
  time_reproduction.py ----------[/heartbeat/condition name]-> SC
  time_reproduction.py ----------[/heartbeat/start / stop]---> SC
  SC が条件倍率を管理し Synth rate を決定する

OSCメッセージ一覧:
  /heartbeat/condition [name]   : 条件切り替え（倍率を SC 側で適用）
  /heartbeat/start              : 振動開始（現在の rawBpm × 条件倍率 で rate 決定）
  /heartbeat/stop               : 振動停止
  /heartbeat/bpm [raw_bpm]      : HW706 からの生BPM更新（倍率を適用してSynth更新）

起動手順:
  1. 管理者コマンドプロンプトで net stop winnat
  2. Woojer を Bluetooth 接続、Windows 出力を「スピーカー (Woojer Strap Edge)」に設定
  3. このファイルを全選択 Ctrl+Enter
  4. python main/scripts/woojer_controller.py
  5. python main/heart_time_experiment/time_reproduction.py
*/

(
// Python用固定OSCポート（sclangのメインポートが変動しても常にここで受信する）
thisProcess.openUDPPort(57055);

Routine {
    // 前の scsynth が完全に終了するまでポーリングで待つ
    if (s.serverRunning) {
        s.quit;
        while ({ s.serverRunning }, { 0.2.wait });
        0.5.wait;  // ポート解放の余裕
    };

    s.options.outDevice  = "WASAPI : スピーカー (Woojer Strap Edge)";
    s.options.inDevice   = "WASAPI : Surfaceステレオマイク";
    s.addr_(NetAddr("127.0.0.1", 57210));

    s.waitForBoot({

        // ===== SynthDef =====
        SynthDef(\fakeHeartbeat, {
            arg out = 0, amp = 0.9, rate = 1.2,
                freq1 = 65, freq2 = 90,
                delay = 0.18, amp1 = 1.0, amp2 = 0.7,
                drive = 2.0, lpfFreq = 150;
            var trig, env1, env2, sig1, sig2, totalSig;
            trig = Impulse.ar(rate);
            env1 = EnvGen.ar(Env.perc(0.005, 0.20), trig);
            sig1 = SinOsc.ar(freq1) * env1 * amp1;
            env2 = EnvGen.ar(Env.perc(0.005, 0.10), DelayC.ar(trig, 0.5, delay));
            sig2 = SinOsc.ar(freq2) * env2 * amp2;
            totalSig = ((sig1 + sig2) * drive).tanh;
            totalSig = LPF.ar(totalSig, lpfFreq);
            Out.ar(out, totalSig.dup * amp);
        }).add;

        // ===== 状態変数 =====
        ~heartbeatSynth   = nil;
        ~currentCondition = "true_heartbeat";
        ~rawBpm           = 72.0;

        // 条件倍率テーブル（パイロット実験で決定後にここを変更する）
        ~conditionMultipliers = Dictionary.newFrom([
            "true_heartbeat", 1.0,
            "fast_false",     1.1,   // パイロット実験結果: ±10%が知覚閾値
            "slow_false",     0.9,
            "control",        1.0
        ]);

        // ===== OSC ハンドラ =====
        // NOTE: callback スレッドから ~func.value を呼ぶと環境が見えないことがある
        //       → ~getAdjustedRate を使わず、各ハンドラにインライン展開する

        // /heartbeat/condition [name]  → 条件設定 + 自動で振動開始
        OSCdef(\setCondition, { |msg|
            try {
                var cond, mult, rate;
                cond = msg[1].asString;
                ~currentCondition = cond;
                mult = ~conditionMultipliers[cond] ? 1.0;
                rate = (~rawBpm * mult) / 60.0;
                if (~heartbeatSynth.notNil) { ~heartbeatSynth.free };
                ~heartbeatSynth = Synth(\fakeHeartbeat, [\rate, rate, \amp, 0.9]);
                ("開始: " ++ cond
                    ++ "  倍率=" ++ mult
                    ++ "  " ++ (rate * 60).round(1) ++ "BPM"
                ).postln;
            } { |e| ("ERROR /heartbeat/condition: " ++ e.errorString).postln };
        }, '/heartbeat/condition');

        // /heartbeat/go  ※ /heartbeat/start は連続送信で2番目が届かないためパス変更
        OSCdef(\startHeartbeat, { |msg|
            try {
                var mult, rate;
                mult = ~conditionMultipliers[~currentCondition] ? 1.0;
                rate = (~rawBpm * mult) / 60.0;
                if (~heartbeatSynth.notNil) { ~heartbeatSynth.free };
                ~heartbeatSynth = Synth(\fakeHeartbeat, [\rate, rate, \amp, 0.9]);
                ("開始: " ++ ~currentCondition
                    ++ "  " ++ (rate * 60).round(1) ++ "BPM"
                ).postln;
            } { |e| ("ERROR /heartbeat/go: " ++ e.errorString).postln };
        }, '/heartbeat/go');

        // /heartbeat/stop
        OSCdef(\stopHeartbeat, { |msg|
            try {
                if (~heartbeatSynth.notNil) {
                    ~heartbeatSynth.free;
                    ~heartbeatSynth = nil;
                };
                "停止".postln;
            } { |e| ("ERROR /heartbeat/stop: " ++ e.errorString).postln };
        }, '/heartbeat/stop');

        // /heartbeat/bpm [raw_bpm]  ← woojer_controller.py が生BPMを送る
        OSCdef(\updateBPM, { |msg|
            try {
                var rawBpm, mult, adjustedBpm, rate;
                rawBpm = msg[1] ? 72;
                ~rawBpm = rawBpm;
                mult = ~conditionMultipliers[~currentCondition] ? 1.0;
                adjustedBpm = rawBpm * mult;
                rate = adjustedBpm / 60.0;
                if (~heartbeatSynth.notNil) {
                    ~heartbeatSynth.set(\rate, rate);
                };
                ("BPM: 実測=" ++ rawBpm.round(1)
                    ++ " → " ++ adjustedBpm.round(1)
                    ++ " [" ++ ~currentCondition ++ "]"
                ).postln;
            } { |e| ("ERROR /heartbeat/bpm: " ++ e.errorString).postln };
        }, '/heartbeat/bpm');

        // /heartbeat/rate [rate]  ← パイロット実験用（倍率テーブルを迂回して直接指定）
        OSCdef(\setRate, { |msg|
            try {
                var rate = msg[1] ? 1.2;
                if (~heartbeatSynth.notNil) { ~heartbeatSynth.free };
                ~heartbeatSynth = Synth(\fakeHeartbeat, [\rate, rate, \amp, 0.9]);
                ("パイロット: " ++ (rate * 60).round(1) ++ "BPM").postln;
            } { |e| ("ERROR /heartbeat/rate: " ++ e.errorString).postln };
        }, '/heartbeat/rate');

        "woojer_heartbeat.scd 読み込み完了".postln;
        ("sclang メインポート : " ++ NetAddr.langPort).postln;
        ("Python用固定ポート  : 57055").postln;
        ("scsynth ポート      : " ++ s.addr.port).postln;
        ("出力デバイス        : " ++ s.options.outDevice).postln;
    });
}.play;
)

// ===== 手動テスト（個別に選択して Ctrl+Enter） =====
// SCIDE から自分自身に OSC を送るには thisProcess.sendMsg を使う（NetAddr("127.0.0.1",...) は自己送信が効かない）

// テスト起動
// thisProcess.sendMsg("/heartbeat/condition", "fast_false");
// thisProcess.sendMsg("/heartbeat/start");

// BPM を手動で送る（woojer_controller.py の代わり）
// thisProcess.sendMsg("/heartbeat/bpm", 72.0);

// 停止
// thisProcess.sendMsg("/heartbeat/stop");

// drive を直接変える（振動の強さ調整）
// ~heartbeatSynth.set(\drive, 3.0);
