(
s.waitForBoot {

    // ============================================================
    // 念のため既存音を停止
    // ============================================================

    s.freeAll;

    // ============================================================
    // 心拍音：左右定位用
    // ============================================================

    SynthDef(\heartbeat_pan, {
        arg out=0, amp=0.6, freq=50, rel=0.2, pan=0;
        var env, sig;

        env = EnvGen.ar(
            Env.perc(0.005, rel),
            doneAction: 2
        );

        sig = SinOsc.ar(freq);
        sig = (sig * 1.5).tanh;
        sig = sig * env * amp;
        sig = LPF.ar(sig, 100);

        Out.ar(out, Pan2.ar(sig, pan));
    }).add;

    // ============================================================
    // 心拍音：左右完全同一用
    // ============================================================

    SynthDef(\heartbeat_both, {
        arg out=0, amp=0.6, freq=50, rel=0.2;
        var env, sig;

        env = EnvGen.ar(
            Env.perc(0.005, rel),
            doneAction: 2
        );

        sig = SinOsc.ar(freq);
        sig = (sig * 1.5).tanh;
        sig = sig * env * amp;
        sig = LPF.ar(sig, 100);

        Out.ar(out, sig ! 2);
    }).add;

    s.sync;

    // ============================================================
    // 変数
    // ============================================================

    ~heartInterval = 60 / 70;
    ~heartScale = 1.0;
    ~lubDubGap = 0.25;

    // v2:
    // "dual" : 左=本来心拍、右=倍率心拍
    // "both" : 左右同一
    ~outputMode = "dual";

    ~leftHeartTask = nil;
    ~rightHeartTask = nil;

    ~isHeartbeatRunning = false;
    ~pendingAutoStart = false;

    ~currentPhase = "none";

    // ============================================================
    // Taskだけ止める
    // ============================================================

    ~stopHeartbeatTasks = {
        if(~leftHeartTask.notNil) {
            ~leftHeartTask.stop;
            ~leftHeartTask = nil;
        };

        if(~rightHeartTask.notNil) {
            ~rightHeartTask.stop;
            ~rightHeartTask = nil;
        };

        ~isHeartbeatRunning = false;
        ~pendingAutoStart = false;
    };

    // ============================================================
    // 停止関数
    // ============================================================

    ~stopHeartbeatSystem = {
        "Stopping heartbeat system...".postln;

        ~stopHeartbeatTasks.value;

        // 鳴り残りを消す
        s.freeAll;
    };

    // ============================================================
    // 左：本来心拍タスク
    // ============================================================

    ~makeLeftHeartTask = {
        Task({
            loop {
                var playInterval;
                var rest;
                var playBpm;

                // 左耳は常に本来心拍 1.00倍
                playInterval = ~heartInterval.clip(0.35, 2.5);
                playBpm = 60 / playInterval;

                ("LEFT original BPM: " ++ playBpm).postln;

                // ドッ
                Synth(\heartbeat_pan, [
                    \freq, 55,
                    \rel, 0.22,
                    \amp, 0.48,
                    \pan, -0.8
                ]);

                ~lubDubGap.wait;

                // クン
                Synth(\heartbeat_pan, [
                    \freq, 48,
                    \rel, 0.14,
                    \amp, 0.33,
                    \pan, -0.8
                ]);

                rest = playInterval - ~lubDubGap;
                rest = rest.max(0.05);

                rest.wait;
            }
        });
    };

    // ============================================================
    // 右：倍率心拍タスク
    // ============================================================

    ~makeRightHeartTask = {
        Task({
            loop {
                var playInterval;
                var rest;
                var playBpm;

                // 右耳は 心拍interval / scale
                // scale > 1.0 なら速くなる
                // scale < 1.0 なら遅くなる
                playInterval = (~heartInterval / ~heartScale).clip(0.35, 2.5);
                playBpm = 60 / playInterval;

                ("RIGHT scaled BPM: " ++ playBpm ++ " scale: " ++ ~heartScale).postln;

                // ドッ
                Synth(\heartbeat_pan, [
                    \freq, 50,
                    \rel, 0.25,
                    \amp, 0.70,
                    \pan, 0.8
                ]);

                ~lubDubGap.wait;

                // クン
                Synth(\heartbeat_pan, [
                    \freq, 45,
                    \rel, 0.15,
                    \amp, 0.50,
                    \pan, 0.8
                ]);

                rest = playInterval - ~lubDubGap;
                rest = rest.max(0.05);

                rest.wait;
            }
        });
    };

    // ============================================================
    // 左右同一タスク
    // ============================================================

    ~makeBothHeartTask = {
        Task({
            loop {
                var playInterval;
                var rest;
                var playBpm;

                playInterval = (~heartInterval / ~heartScale).clip(0.35, 2.5);
                playBpm = 60 / playInterval;

                ("BOTH BPM: " ++ playBpm ++ " scale: " ++ ~heartScale).postln;

                // ドッ
                Synth(\heartbeat_both, [
                    \freq, 50,
                    \rel, 0.25,
                    \amp, 0.65
                ]);

                ~lubDubGap.wait;

                // クン
                Synth(\heartbeat_both, [
                    \freq, 45,
                    \rel, 0.15,
                    \amp, 0.45
                ]);

                rest = playInterval - ~lubDubGap;
                rest = rest.max(0.05);

                rest.wait;
            }
        });
    };

    // ============================================================
    // 開始関数
    // ============================================================

    ~startHeartbeatSystem = {
        if(~isHeartbeatRunning.not, {

            "Starting heartbeat system...".postln;
            ("outputMode: " ++ ~outputMode).postln;
            ("heartScale: " ++ ~heartScale).postln;
            ("phase: " ++ ~currentPhase).postln;

            ~isHeartbeatRunning = true;
            ~pendingAutoStart = false;

            ~stopHeartbeatTasks.value;
            ~isHeartbeatRunning = true;

            if(~outputMode == "both", {

                // both:
                // 左右同一で鳴らす
                "Mode both: same heartbeat pulse to both ears.".postln;

                ~rightHeartTask = ~makeBothHeartTask.value;
                ~rightHeartTask.play;

            }, {

                // dual:
                // 左=本来心拍
                // 右=倍率心拍
                "Mode dual: LEFT original heartbeat, RIGHT scaled heartbeat.".postln;

                ~leftHeartTask = ~makeLeftHeartTask.value;
                ~leftHeartTask.play;

                ~rightHeartTask = ~makeRightHeartTask.value;
                ~rightHeartTask.play;
            });

        }, {
            "Heartbeat system already running.".postln;
        });
    };

    // ============================================================
    // 出力モード設定
    // ============================================================

    ~setOutputMode = { |mode|
        var modeString;
        var oldMode;
        var newMode;

        oldMode = ~outputMode;
        modeString = mode.asString;

        if(modeString == "both", {
            newMode = "both";
        }, {
            newMode = "dual";
        });

        ~outputMode = newMode;

        ("output mode set to: " ++ ~outputMode).postln;

        if(~isHeartbeatRunning and: { oldMode != ~outputMode }, {
            "Output mode changed while running. Restarting...".postln;
            ~stopHeartbeatTasks.value;
            ~startHeartbeatSystem.value;
        });
    };

    // ============================================================
    // 遅延自動開始
    // ============================================================

    ~scheduleDelayedAutoStart = {
        if(~isHeartbeatRunning.not and: { ~pendingAutoStart.not }, {
            ~pendingAutoStart = true;

            AppClock.sched(0.15, {
                ~pendingAutoStart = false;

                if(~isHeartbeatRunning.not, {
                    "Delayed auto-start after /heart/interval.".postln;
                    ("delayed outputMode: " ++ ~outputMode).postln;
                    ("delayed heartScale: " ++ ~heartScale).postln;
                    ~startHeartbeatSystem.value;
                });

                nil;
            });
        });
    };

    // ============================================================
    // OSC受信
    // ============================================================

    OSCdef(\receiveHeartInterval, { |msg|
        var newInterval;

        newInterval = msg[1].asFloat;

        if(newInterval > 0.25 and: { newInterval < 2.5 }, {
            ~heartInterval = newInterval;
            ("heart interval: " ++ ~heartInterval).postln;

            // /heart/startが届かない場合でも開始できるように保険で残す
            ~scheduleDelayedAutoStart.value;

        }, {
            ("invalid interval ignored: " ++ newInterval).postln;
        });

    }, '/heart/interval');

    OSCdef(\receiveRawBpm, { |msg|
        ("raw BPM: " ++ msg[1]).postln;
    }, '/heart/raw_bpm');

    OSCdef(\receiveSmoothedBpm, { |msg|
        ("smoothed BPM: " ++ msg[1]).postln;
    }, '/heart/smoothed_bpm');

    OSCdef(\receiveBpmUsed, { |msg|
        ("bpm used for sound: " ++ msg[1]).postln;
    }, '/heart/bpm_used');

    OSCdef(\receiveHeartScale, { |msg|
        var newScale;

        newScale = msg[1].asFloat;

        if(newScale > 0.3 and: { newScale < 3.0 }, {
            ~heartScale = newScale;
            ("heart scale set to: " ++ ~heartScale).postln;
        }, {
            ("invalid scale ignored: " ++ newScale).postln;
        });

    }, '/heart/scale');

    OSCdef(\receiveOutputMode, { |msg|
        var mode;

        mode = msg[1].asString;
        ~setOutputMode.value(mode);

    }, '/heart/output_mode');

    OSCdef(\receivePhase, { |msg|
        ~currentPhase = msg[1].asString;
        ("phase set to: " ++ ~currentPhase).postln;
    }, '/heart/phase');

    OSCdef(\receiveHeartStart, { |msg|
        "received /heart/start".postln;
        ("start outputMode: " ++ ~outputMode).postln;
        ("start heartScale: " ++ ~heartScale).postln;

        ~startHeartbeatSystem.value;
    }, '/heart/start');

    OSCdef(\receiveHeartStop, { |msg|
        "received /heart/stop".postln;
        ~stopHeartbeatSystem.value;
    }, '/heart/stop');

    // ============================================================
    // 起動メッセージ
    // ============================================================

    "Heartbeat Watanabe ramp system v2 is ready.".postln;
    "Python: hw706_v2.py".postln;
    "Mode dual: LEFT original heartbeat, RIGHT scaled heartbeat.".postln;
    "baseline/recovery: Python stops sound.".postln;
    "sync/ramp/hold: Python starts sound and updates /heart/scale.".postln;
    "Run Python to start.".postln;
};
)