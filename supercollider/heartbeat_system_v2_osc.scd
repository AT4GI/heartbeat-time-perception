(
s.waitForBoot {

    // ============================================================
    // Time production v2 OSC heartbeat system
    // PsychoPy: psychopy_experiment_v2_osc.py
    // ============================================================

    // 既存コードと衝突しにくいように、変数名とOSCdef名は tpV2 系に統一する。

    SynthDef(\tpV2HeartbeatPulse, {
        arg out=0, amp=0.55, freq=50, rel=0.18;
        var env, sig;

        env = EnvGen.ar(
            Env.perc(0.005, rel),
            doneAction: 2
        );

        sig = SinOsc.ar(freq);
        sig = (sig * 1.5).tanh;
        sig = LPF.ar(sig * env * amp, 120);

        Out.ar(out, sig ! 2);
    }).add;

    s.sync;

    // ============================================================
    // 状態変数
    // ============================================================

    ~tpV2HeartInterval = 60 / 70; // 心拍ロガー未接続時の仮interval
    ~tpV2CurrentCondition = "silent";
    ~tpV2CurrentScale = 1.0;
    ~tpV2CurrentTrialNum = -1;
    ~tpV2SoundEnabled = false;
    ~tpV2HeartTask = nil;
    ~tpV2LubDubGap = 0.22;

    // ============================================================
    // 条件名から倍率を決める
    // heart interval * scale で再生周期を作る。
    // scale < 1.0 は速く、scale > 1.0 は遅くなる。
    // ============================================================

    ~tpV2ScaleForCondition = { |condition|
        var cond;

        cond = condition.asString;

        if(cond == "heart_0.75x", {
            0.75;
        }, {
            if(cond == "heart_1.25x", {
                1.25;
            }, {
                1.0;
            });
        });
    };

    // ============================================================
    // 心拍音タスク
    // ============================================================

    ~tpV2MakeHeartTask = {
        Task({
            loop {
                var playInterval;
                var rest;
                var playBpm;

                if(~tpV2SoundEnabled and: { ~tpV2CurrentCondition != "silent" }, {
                    playInterval = (~tpV2HeartInterval * ~tpV2CurrentScale).clip(0.35, 2.5);
                    playBpm = 60 / playInterval;

                    (
                        "tpV2 pulse BPM: " ++ playBpm
                        ++ " condition: " ++ ~tpV2CurrentCondition
                        ++ " scale: " ++ ~tpV2CurrentScale
                        ++ " trial_num: " ++ ~tpV2CurrentTrialNum
                    ).postln;

                    // ドッ
                    Synth(\tpV2HeartbeatPulse, [
                        \freq, 52,
                        \rel, 0.22,
                        \amp, 0.60
                    ]);

                    ~tpV2LubDubGap.wait;

                    // クン
                    Synth(\tpV2HeartbeatPulse, [
                        \freq, 45,
                        \rel, 0.14,
                        \amp, 0.42
                    ]);

                    rest = playInterval - ~tpV2LubDubGap;
                    rest = rest.max(0.05);
                    rest.wait;
                }, {
                    0.05.wait;
                });
            }
        });
    };

    // ============================================================
    // 開始・停止関数
    // ============================================================

    ~tpV2StartSound = {
        ~tpV2SoundEnabled = true;

        if(~tpV2CurrentCondition == "silent", {
            "tpV2 silent condition: sound disabled.".postln;
        }, {
            if(~tpV2HeartTask.isNil, {
                ~tpV2HeartTask = ~tpV2MakeHeartTask.value;
                ~tpV2HeartTask.play;
            });
        });

        (
            "tpV2 start | condition: " ++ ~tpV2CurrentCondition
            ++ " | scale: " ++ ~tpV2CurrentScale
            ++ " | trial_num: " ++ ~tpV2CurrentTrialNum
        ).postln;
    };

    ~tpV2StopSound = {
        ~tpV2SoundEnabled = false;

        if(~tpV2HeartTask.notNil, {
            ~tpV2HeartTask.stop;
            ~tpV2HeartTask = nil;
        });

        "tpV2 sound stopped.".postln;
    };

    // ============================================================
    // 心拍ロガーからのOSC受信
    // 既存Pythonロガーが送る interval または bpm を利用する。
    // ============================================================

    OSCdef(\tpV2ReceiveHeartInterval, { |msg|
        var newInterval;

        newInterval = msg[1].asFloat;

        if(newInterval > 0.25 and: { newInterval < 2.5 }, {
            ~tpV2HeartInterval = newInterval;
            ("tpV2 heart interval: " ++ ~tpV2HeartInterval).postln;
        }, {
            ("tpV2 invalid interval ignored: " ++ newInterval).postln;
        });

    }, '/heart/interval');

    OSCdef(\tpV2ReceiveBpmUsed, { |msg|
        var bpm;

        bpm = msg[1].asFloat;

        if(bpm > 30 and: { bpm < 220 }, {
            ~tpV2HeartInterval = 60 / bpm;
            ("tpV2 bpm used: " ++ bpm ++ " interval: " ++ ~tpV2HeartInterval).postln;
        }, {
            ("tpV2 invalid bpm ignored: " ++ bpm).postln;
        });

    }, '/heart/bpm_used');

    OSCdef(\tpV2ReceiveSmoothedBpm, { |msg|
        var bpm;

        bpm = msg[1].asFloat;

        if(bpm > 30 and: { bpm < 220 }, {
            ~tpV2HeartInterval = 60 / bpm;
            ("tpV2 smoothed bpm: " ++ bpm ++ " interval: " ++ ~tpV2HeartInterval).postln;
        });

    }, '/heart/smoothed_bpm');

    // ============================================================
    // PsychoPyからのOSC受信
    // /trial/start: condition, target_duration, trial_num
    // /trial/stop : condition, trial_num
    // ============================================================

    OSCdef(\tpV2ReceiveTrialStart, { |msg|
        var condition;
        var targetDuration;
        var trialNum;

        condition = msg[1].asString;
        targetDuration = msg[2].asFloat;
        trialNum = msg[3].asInteger;

        ~tpV2CurrentCondition = condition;
        ~tpV2CurrentScale = ~tpV2ScaleForCondition.value(condition);
        ~tpV2CurrentTrialNum = trialNum;

        (
            "tpV2 received /trial/start"
            ++ " | condition: " ++ ~tpV2CurrentCondition
            ++ " | target_duration: " ++ targetDuration
            ++ " | scale: " ++ ~tpV2CurrentScale
            ++ " | trial_num: " ++ ~tpV2CurrentTrialNum
        ).postln;

        ~tpV2StartSound.value;

    }, '/trial/start');

    OSCdef(\tpV2ReceiveTrialStop, { |msg|
        var condition;
        var trialNum;

        condition = msg[1].asString;
        trialNum = msg[2].asInteger;

        (
            "tpV2 received /trial/stop"
            ++ " | condition: " ++ condition
            ++ " | current_condition: " ++ ~tpV2CurrentCondition
            ++ " | scale: " ++ ~tpV2CurrentScale
            ++ " | trial_num: " ++ trialNum
        ).postln;

        ~tpV2StopSound.value;

    }, '/trial/stop');

    // ============================================================
    // 起動メッセージ
    // ============================================================

    "heartbeat_system_v2_osc.scd is ready.".postln;
    "Waiting for PsychoPy /trial/start and /trial/stop.".postln;
    "Listening for heart logger OSC: /heart/interval, /heart/bpm_used, /heart/smoothed_bpm.".postln;
    "OSC port should be SuperCollider default NetAddr.langPort, usually 57120.".postln;
};
)
