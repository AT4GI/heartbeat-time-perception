(
s.waitForBoot {

    // =========================
    // 心拍っぽい音：ドッ・クン用
    // =========================

    SynthDef(\heartbeat_simple, {
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

    s.sync;


    // =========================
    // 変数
    // =========================

    ~heartInterval = 60 / 70;
    ~heartScale = 1.0;
    ~fixedBpm = 60;
    ~lubDubGap = 0.25;

    ~fixedPulseTask = nil;
    ~heartPulseTask = nil;

    // 音が鳴っているかどうか
    ~isHeartbeatRunning = false;


    // =========================
    // 停止関数
    // =========================

    ~stopHeartbeatSystem = {
        "Stopping heartbeat system...".postln;

        if(~fixedPulseTask.notNil) {
            ~fixedPulseTask.stop;
            ~fixedPulseTask = nil;
        };

        if(~heartPulseTask.notNil) {
            ~heartPulseTask.stop;
            ~heartPulseTask = nil;
        };

        ~isHeartbeatRunning = false;
    };


    // =========================
    // 開始関数
    // =========================

    ~startHeartbeatSystem = {
        if(~isHeartbeatRunning.not, {

            "Starting heartbeat system...".postln;
            ("heartScale: " ++ ~heartScale).postln;

            ~isHeartbeatRunning = true;

            // 念のため既存Taskを止める
            if(~fixedPulseTask.notNil) {
                ~fixedPulseTask.stop;
                ~fixedPulseTask = nil;
            };

            if(~heartPulseTask.notNil) {
                ~heartPulseTask.stop;
                ~heartPulseTask = nil;
            };


            // =========================
            // 左：固定BPMの心拍音
            // =========================

            ~fixedPulseTask = Task({
                loop {
                    var fixedInterval;
                    var rest;

                    fixedInterval = 60 / ~fixedBpm;

                    // ドッ
                    Synth(\heartbeat_simple, [
                        \freq, 55,
                        \rel, 0.22,
                        \amp, 0.45,
                        \pan, -0.8
                    ]);

                    ~lubDubGap.wait;

                    // クン
                    Synth(\heartbeat_simple, [
                        \freq, 48,
                        \rel, 0.14,
                        \amp, 0.32,
                        \pan, -0.8
                    ]);

                    rest = fixedInterval - ~lubDubGap;
                    rest = rest.max(0.05);

                    rest.wait;
                }
            }).play;


            // =========================
            // 右：心拍由来intervalの心拍音
            // =========================

            ~heartPulseTask = Task({
                loop {
                    var playInterval;
                    var rest;
                    var playBpm;

                    playInterval = (~heartInterval / ~heartScale).clip(0.35, 2.5);
                    playBpm = 60 / playInterval;

                    ("right play BPM: " ++ playBpm).postln;

                    // ドッ
                    Synth(\heartbeat_simple, [
                        \freq, 50,
                        \rel, 0.25,
                        \amp, 0.7,
                        \pan, 0.8
                    ]);

                    ~lubDubGap.wait;

                    // クン
                    Synth(\heartbeat_simple, [
                        \freq, 45,
                        \rel, 0.15,
                        \amp, 0.5,
                        \pan, 0.8
                    ]);

                    rest = playInterval - ~lubDubGap;
                    rest = rest.max(0.05);

                    rest.wait;
                }
            }).play;

        }, {
            // すでに鳴っている場合は何もしない
            "Heartbeat system already running.".postln;
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
            // /heart/start が届かなくても、
            // 最初の有効な /heart/interval が届いたら自動開始する
            if(~isHeartbeatRunning.not, {
                "Auto-start by first valid /heart/interval.".postln;
                ~startHeartbeatSystem.value;
            });

        }, {
            ("invalid interval ignored: " ++ newInterval).postln;
        });

    }, '/heart/interval');


    OSCdef(\receiveSmoothedBpm, { |msg|
        ("smoothed BPM: " ++ msg[1]).postln;
    }, '/heart/smoothed_bpm');


    OSCdef(\receiveHeartScale, { |msg|
        var newScale;

        newScale = msg[1].asFloat;

        if(newScale > 0.3 and: { newScale < 2.0 }, {
            ~heartScale = newScale;
            ("heart scale set to: " ++ ~heartScale).postln;
        }, {
            ("invalid scale ignored: " ++ newScale).postln;
        });

    }, '/heart/scale');


    OSCdef(\receiveHeartStart, { |msg|
        "received /heart/start".postln;
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
    "Sound will also auto-start when /heart/interval arrives.".postln;
    "Python will send /heart/stop at the end.".postln;
};
)
~startHeartbeatSystem.value;
~stopHeartbeatSystem.value;