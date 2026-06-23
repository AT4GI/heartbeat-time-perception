(
s.waitForBoot {

    // =========================
    // 念のため既存音を停止
    // =========================

    s.freeAll;

    // =========================
    // 心拍音：左右定位用
    // split モードで使う
    // =========================

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


    // =========================
    // 心拍音：左右完全同一用
    // both モードで使う
    // =========================

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

        // 左右に完全に同じ信号を出す
        Out.ar(out, sig ! 2);
    }).add;

    s.sync;


    // =========================
    // 変数
    // =========================

    ~heartInterval = 60 / 70;
    ~heartScale = 1.0;
    ~fixedBpm = 60;
    ~lubDubGap = 0.25;

    // "both"  : 心拍由来音だけを左右同一に出す
    // "split" : 左=固定BPM、右=心拍倍率音
    ~outputMode = "split";

    ~fixedPulseTask = nil;
    ~heartPulseTask = nil;

    ~isHeartbeatRunning = false;

    // /heart/interval による遅延自動開始が重複しないためのフラグ
    ~pendingAutoStart = false;


    // =========================
    // Taskだけ止める関数
    // =========================

    ~stopHeartbeatTasks = {
        if(~fixedPulseTask.notNil) {
            ~fixedPulseTask.stop;
            ~fixedPulseTask = nil;
        };

        if(~heartPulseTask.notNil) {
            ~heartPulseTask.stop;
            ~heartPulseTask = nil;
        };

        ~isHeartbeatRunning = false;
        ~pendingAutoStart = false;
    };


    // =========================
    // 停止関数
    // =========================

    ~stopHeartbeatSystem = {
        "Stopping heartbeat system...".postln;

        ~stopHeartbeatTasks.value;

        // 鳴り残りを消す
        s.freeAll;
    };


    // =========================
    // 左：固定BPMタスク
    // split モードだけで使う
    // =========================

    ~makeFixedPulseTask = {
        Task({
            loop {
                var fixedInterval;
                var rest;

                fixedInterval = 60 / ~fixedBpm;

                // ドッ：左
                Synth(\heartbeat_pan, [
                    \freq, 55,
                    \rel, 0.22,
                    \amp, 0.45,
                    \pan, -0.8
                ]);

                ~lubDubGap.wait;

                // クン：左
                Synth(\heartbeat_pan, [
                    \freq, 48,
                    \rel, 0.14,
                    \amp, 0.32,
                    \pan, -0.8
                ]);

                rest = fixedInterval - ~lubDubGap;
                rest = rest.max(0.05);

                rest.wait;
            }
        });
    };


    // =========================
    // 心拍由来タスク
    //
    // both モード：
    //   心拍由来音を左右同一に出す
    //
    // split モード：
    //   心拍由来音を右耳に出す
    // =========================

    ~makeHeartPulseTask = {
        Task({
            loop {
                var playInterval;
                var rest;
                var playBpm;

                playInterval = (~heartInterval / ~heartScale).clip(0.35, 2.5);
                playBpm = 60 / playInterval;

                if(~outputMode == "both", {

                    ("BOTH ears play BPM: " ++ playBpm).postln;

                    // ドッ：左右同一
                    Synth(\heartbeat_both, [
                        \freq, 50,
                        \rel, 0.25,
                        \amp, 0.7
                    ]);

                    ~lubDubGap.wait;

                    // クン：左右同一
                    Synth(\heartbeat_both, [
                        \freq, 45,
                        \rel, 0.15,
                        \amp, 0.5
                    ]);

                }, {

                    ("RIGHT play BPM: " ++ playBpm).postln;

                    // ドッ：右
                    Synth(\heartbeat_pan, [
                        \freq, 50,
                        \rel, 0.25,
                        \amp, 0.7,
                        \pan, 0.8
                    ]);

                    ~lubDubGap.wait;

                    // クン：右
                    Synth(\heartbeat_pan, [
                        \freq, 45,
                        \rel, 0.15,
                        \amp, 0.5,
                        \pan, 0.8
                    ]);
                });

                rest = playInterval - ~lubDubGap;
                rest = rest.max(0.05);

                rest.wait;
            }
        });
    };


    // =========================
    // 開始関数
    // =========================

    ~startHeartbeatSystem = {
        if(~isHeartbeatRunning.not, {

            "Starting heartbeat system...".postln;
            ("heartScale: " ++ ~heartScale).postln;
            ("outputMode: " ++ ~outputMode).postln;

            ~isHeartbeatRunning = true;
            ~pendingAutoStart = false;

            // 念のため既存Taskを止める
            if(~fixedPulseTask.notNil) {
                ~fixedPulseTask.stop;
                ~fixedPulseTask = nil;
            };

            if(~heartPulseTask.notNil) {
                ~heartPulseTask.stop;
                ~heartPulseTask = nil;
            };

            if(~outputMode == "both", {

                // =========================
                // both モード
                // 1.00倍かつ音あり条件
                //
                // 固定左BPMは鳴らさない。
                // 心拍由来音だけを左右両耳に鳴らす。
                // =========================

                "Mode both: ONLY heart-derived pulse is sent to BOTH ears.".postln;

                ~heartPulseTask = ~makeHeartPulseTask.value;
                ~heartPulseTask.play;

            }, {

                // =========================
                // split モード
                // 1.00倍以外の音条件
                //
                // 左：固定BPM
                // 右：心拍由来 interval / heartScale
                // =========================

                "Mode split: fixed pulse LEFT, scaled heart pulse RIGHT.".postln;

                ~fixedPulseTask = ~makeFixedPulseTask.value;
                ~fixedPulseTask.play;

                ~heartPulseTask = ~makeHeartPulseTask.value;
                ~heartPulseTask.play;
            });

        }, {
            "Heartbeat system already running.".postln;
        });
    };


    // =========================
    // 出力モード設定
    // =========================

    ~setOutputMode = { |mode|
        var modeString;
        var oldMode;
        var newMode;

        oldMode = ~outputMode;
        modeString = mode.asString;

        if(modeString == "both", {
            newMode = "both";
        }, {
            newMode = "split";
        });

        ~outputMode = newMode;

        ("output mode set to: " ++ ~outputMode).postln;

        // もし何らかの理由で走行中にモードが変わった場合は、
        // 正しいモードで再起動する
        if(~isHeartbeatRunning and: { oldMode != ~outputMode }, {
            "Output mode changed while running. Restarting heartbeat system...".postln;
            ~stopHeartbeatTasks.value;
            ~startHeartbeatSystem.value;
        });
    };


    // =========================
    // 遅延自動開始
    // =========================

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


    // =========================
    // OSC受信
    // =========================

    OSCdef(\receiveHeartInterval, { |msg|
        var newInterval;

        newInterval = msg[1].asFloat;

        if(newInterval > 0.25 and: { newInterval < 2.5 }, {
            ~heartInterval = newInterval;
            ("heart interval: " ++ ~heartInterval).postln;

            // 重要：
            // 即時開始はしない。
            // 0.15秒待ってから開始する。
            // これにより /heart/output_mode と /heart/scale が届いてから
            // 正しい both / split モードで開始できる。
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


    OSCdef(\receiveHeartStart, { |msg|
        "received /heart/start".postln;
        ("start outputMode: " ++ ~outputMode).postln;
        ("start heartScale: " ++ ~heartScale).postln;

        // /heart/start が来た場合はすぐ開始する。
        // すでに遅延自動開始が予約されていても、
        // ~isHeartbeatRunning が true になるので二重開始されない。
        ~startHeartbeatSystem.value;
    }, '/heart/start');


    OSCdef(\receiveHeartStop, { |msg|
        "received /heart/stop".postln;
        ~stopHeartbeatSystem.value;
    }, '/heart/stop');


    // =========================
    // 起動メッセージ
    // =========================

    "Heartbeat system is ready.".postln;
    "Run Python to start sound automatically.".postln;
    "1.00x + SEND_SOUND_TO_SC=True -> both ears.".postln;
    "Other scales, e.g. 0.75 / 1.25 / 1.50 -> split mode.".postln;
    "Safety: /heart/interval schedules delayed auto-start after 0.15 sec.".postln;
    "Python will send /heart/stop at the end.".postln;
};
)