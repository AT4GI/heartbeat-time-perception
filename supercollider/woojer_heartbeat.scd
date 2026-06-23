/*
woojer_heartbeat.scd
--------------------
Woojer Strap Edge 用 偽心拍振動パッチ
- HW706 から Python 経由で OSC を受け取り、BPM に同期した振動を生成する
- 振動のみ（可聴音なし）: 20〜50Hz 帯域の超低周波サイン波を使用
- 偽心拍条件: rate を実際のBPMから±%操作して提示する

使い方:
  1. このファイルを全選択して Ctrl+Enter で起動
  2. Python スクリプト (woojer_controller.py) を起動して OSC を送信
  3. Woojer を Bluetooth でパソコンに接続しておく
  4. パソコンの音声出力を「Woojer Strap Edge」に設定しておく
*/

(
// ===== サーバー設定 =====
s.options.outDevice = "Woojer Strap Edge"; // Bluetooth接続のWoojerを出力先に指定
// ※ 上の行が効かない場合はSuperCollider起動後にサーバーを再起動すること
// s.reboot;

s.waitForBoot({

    // ===== SynthDef: 偽心拍振動 =====
    // Geminiの設計に基づく2峰性波形（Lubb-Dupp）
    SynthDef(\fakeHeartbeat, {
        arg out = 0,
            amp = 0.9,       // 全体の振幅（振動の強さ）
            rate = 1.2,      // 拍数/秒（1.2 = 72BPM）
            freq1 = 32,      // 第一音の周波数（Hz）: 低め・長め
            freq2 = 45,      // 第二音の周波数（Hz）: 高め・短め
            delay = 0.18,    // 第二音の遅延時間（秒）
            amp1 = 1.0,      // 第一音の相対振幅
            amp2 = 0.8,      // 第二音の相対振幅
            lpfFreq = 60;    // ローパスフィルタのカットオフ（Hz）

        var trig, env1, env2, sig1, sig2, totalSig;

        // トリガー: rate に応じた周期で発火
        trig = Impulse.ar(rate);

        // 第一音（ト / Lubb）: 房室弁が閉じる音、低めでやや長い
        env1 = EnvGen.ar(Env.perc(0.005, 0.15), trig);
        sig1 = SinOsc.ar(freq1) * env1 * amp1;

        // 第二音（クン / Dupp）: 半月弁が閉じる音、高めで鋭く短い
        env2 = EnvGen.ar(Env.perc(0.005, 0.08), DelayC.ar(trig, 0.5, delay));
        sig2 = SinOsc.ar(freq2) * env2 * amp2;

        // 2つの波をブレンド
        totalSig = sig1 + sig2;

        // ローパスフィルタ: 可聴域の高音成分をカット
        totalSig = LPF.ar(totalSig, lpfFreq);

        // ステレオ出力（Woojerはステレオ入力）
        Out.ar(out, totalSig.dup * amp);
    }).add;

    // ===== OSC受信設定 =====
    // Python (woojer_controller.py) から以下のOSCメッセージを受け取る
    //   /heartbeat/start  [rate]  : 心拍振動を開始
    //   /heartbeat/stop          : 心拍振動を停止
    //   /heartbeat/bpm   [bpm]   : BPMをリアルタイム更新

    ~heartbeatSynth = nil;

    // 振動開始: /heartbeat/start [rate(拍/秒)]
    OSCdef(\startHeartbeat, { |msg|
        var rate = msg[1] ? 1.2;
        if (~heartbeatSynth.notNil) { ~heartbeatSynth.free };
        ~heartbeatSynth = Synth(\fakeHeartbeat, [\rate, rate, \amp, 0.9]);
        ("開始: rate=" ++ rate ++ " (" ++ (rate * 60).round(1) ++ "BPM)").postln;
    }, '/heartbeat/start');

    // 振動停止: /heartbeat/stop
    OSCdef(\stopHeartbeat, { |msg|
        if (~heartbeatSynth.notNil) {
            ~heartbeatSynth.free;
            ~heartbeatSynth = nil;
        };
        "停止".postln;
    }, '/heartbeat/stop');

    // BPMリアルタイム更新: /heartbeat/bpm [bpm]
    OSCdef(\updateBPM, { |msg|
        var bpm = msg[1] ? 72;
        var rate = bpm / 60.0;
        if (~heartbeatSynth.notNil) {
            ~heartbeatSynth.set(\rate, rate);
        };
        ("BPM更新: " ++ bpm ++ " -> rate=" ++ rate.round(0.001)).postln;
    }, '/heartbeat/bpm');

    // ===== 条件別のrate計算ヘルパー =====
    // 実際のBPMから各条件のrateを計算する関数
    ~calcRate = { |baseBpm, condition|
        // condition: \true_heartbeat, \fast_false, \slow_false, \control
        var multiplier = switch(condition,
            \true_heartbeat, { 1.0  },   // 等倍（本物条件）
            \fast_false,     { 1.2  },   // 20%速い（偽条件・速）← パイロットで調整
            \slow_false,     { 0.8  },   // 20%遅い（偽条件・遅）← パイロットで調整
            \control,        { 1.0  }    // 等倍（統制条件・教示のみ異なる）
        );
        (baseBpm * multiplier) / 60.0;
    };

    "woojer_heartbeat.scd 読み込み完了".postln;
    "OSC受信ポート: 57120".postln;
    "送信コマンド例:".postln;
    "  /heartbeat/start [rate]  : 振動開始".postln;
    "  /heartbeat/stop          : 振動停止".postln;
    "  /heartbeat/bpm [bpm]     : BPM更新".postln;
});
)

// ===== 手動テスト用コマンド（個別に実行） =====

// テスト1: 72BPM で振動開始
// x = Synth(\fakeHeartbeat, [\rate, 72/60, \amp, 0.9]);

// テスト2: BPMを変える
// x.set(\rate, 80/60);  // 80BPMに変更

// テスト3: 振幅を変える
// x.set(\amp, 0.5);

// テスト4: 停止
// x.free;

// ===== パイロット実験用: ズレ幅テスト =====
// 被験者に各ズレ幅を聴かせて「自分の心拍か」を確認する

// 基準BPM（実際に測定してから入れる）
// ~baseBpm = 72;

// 等倍（本物相当）
// x = Synth(\fakeHeartbeat, [\rate, ~baseBpm/60, \amp, 0.9]);

// 5%速い
// x.set(\rate, (~baseBpm * 1.05) / 60);

// 10%速い
// x.set(\rate, (~baseBpm * 1.10) / 60);

// 15%速い
// x.set(\rate, (~baseBpm * 1.15) / 60);

// 20%速い
// x.set(\rate, (~baseBpm * 1.20) / 60);

// 25%速い
// x.set(\rate, (~baseBpm * 1.25) / 60);

// 停止
// x.free;
