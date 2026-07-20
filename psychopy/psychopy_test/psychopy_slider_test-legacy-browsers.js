/***************************** 
 * Psychopy_Slider_Test *
 *****************************/


// store info about the experiment session:
let expName = 'psychopy_slider_test';  // from the Builder filename that created this script
let expInfo = {
    'participant': `${util.pad(Number.parseFloat(util.randint(0, 999999)).toFixed(0), 6)}`,
    'session': '001',
};
let PILOTING = util.getUrlParameters().has('__pilotToken');

// Start code blocks for 'Before Experiment'
// init psychoJS:
const psychoJS = new PsychoJS({
  debug: true
});

// open window:
psychoJS.openWindow({
  fullscr: true,
  color: new util.Color([0,0,0]),
  units: 'height',
  waitBlanking: true,
  backgroundImage: '',
  backgroundFit: 'none',
});
// schedule the experiment:
psychoJS.schedule(psychoJS.gui.DlgFromDict({
  dictionary: expInfo,
  title: expName
}));

const flowScheduler = new Scheduler(psychoJS);
const dialogCancelScheduler = new Scheduler(psychoJS);
psychoJS.scheduleCondition(function() { return (psychoJS.gui.dialogComponent.button === 'OK'); },flowScheduler, dialogCancelScheduler);

// flowScheduler gets run if the participants presses OK
flowScheduler.add(updateInfo); // add timeStamp
flowScheduler.add(experimentInit);
flowScheduler.add(trialRoutineBegin());
flowScheduler.add(trialRoutineEachFrame());
flowScheduler.add(trialRoutineEnd());
flowScheduler.add(quitPsychoJS, 'ご協力ありがとうございました.', true);

// quit if user presses Cancel in dialog box:
dialogCancelScheduler.add(quitPsychoJS, 'ご協力ありがとうございました.', false);

psychoJS.start({
  expName: expName,
  expInfo: expInfo,
  resources: [
    // resources:
  ]
});

psychoJS.experimentLogger.setLevel(core.Logger.ServerLevel.INFO);


var currentLoop;
var frameDur;
async function updateInfo() {
  currentLoop = psychoJS.experiment;  // right now there are no loops
  expInfo['date'] = util.MonotonicClock.getDateStr();  // add a simple timestamp
  expInfo['expName'] = expName;
  expInfo['psychopyVersion'] = '2026.1.3';
  expInfo['OS'] = window.navigator.platform;


  // store frame rate of monitor if we can measure it successfully
  expInfo['frameRate'] = psychoJS.window.getActualFrameRate();
  if (typeof expInfo['frameRate'] !== 'undefined')
    frameDur = 1.0 / Math.round(expInfo['frameRate']);
  else
    frameDur = 1.0 / 60.0; // couldn't get a reliable measure so guess

  // add info from the URL:
  util.addInfoFromUrl(expInfo);
  

  
  psychoJS.experiment.dataFileName = (("." + "/") + `data/${expInfo["participant"]}_${expName}_${expInfo["date"]}`);
  psychoJS.experiment.field_separator = '\t';


  return Scheduler.Event.NEXT;
}


var trialClock;
var question_text;
var rating_time_long;
var label_left;
var label_right;
var globalClock;
var routineTimer;
async function experimentInit() {
  // Initialize components for Routine "trial"
  trialClock = new util.Clock();
  question_text = new visual.TextStim({
    win: psychoJS.window,
    name: 'question_text',
    text: '今の音を聴いて、時間が長く感じましたか？\nDid the sound make the time feel longer?\n\n1 = 全くそう思わない / Strongly disagree\n7 = とてもそう思う / Strongly agree',
    font: 'Arial',
    units: undefined, 
    pos: [0, 0.32], draggable: false, height: 0.045,  wrapWidth: undefined, ori: 0.0,
    languageStyle: 'LTR',
    color: new util.Color('white'),  opacity: undefined,
    depth: 0.0 
  });
  
  rating_time_long = new visual.Slider({
    win: psychoJS.window, name: 'rating_time_long',
    startValue: undefined,
    size: [1.1, 0.08], pos: [0, (- 0.15)], ori: 0.0, units: psychoJS.window.units,
    labels: undefined, fontSize: 0.05, ticks: [1, 2, 3, 4, 5, 6, 7],
    granularity: 1.0, style: ["RATING"],
    color: new util.Color('LightGray'), markerColor: new util.Color('Red'), lineColor: new util.Color('White'), 
    opacity: undefined, fontFamily: 'Noto Sans', bold: true, italic: false, depth: -1, 
    flip: false,
  });
  
  label_left = new visual.TextStim({
    win: psychoJS.window,
    name: 'label_left',
    text: '1\n全くそう思わない\nStrongly disagree',
    font: 'Arial',
    units: undefined, 
    pos: [(- 0.42), (- 0.38)], draggable: false, height: 0.045,  wrapWidth: undefined, ori: 0.0,
    languageStyle: 'LTR',
    color: new util.Color('white'),  opacity: undefined,
    depth: -2.0 
  });
  
  label_right = new visual.TextStim({
    win: psychoJS.window,
    name: 'label_right',
    text: '7\nとてもそう思う\nStrongly agree',
    font: 'Arial',
    units: undefined, 
    pos: [0.42, (- 0.38)], draggable: false, height: 0.045,  wrapWidth: undefined, ori: 0.0,
    languageStyle: 'LTR',
    color: new util.Color('white'),  opacity: undefined,
    depth: -3.0 
  });
  
  // Create some handy timers
  globalClock = new util.Clock();  // to track the time since experiment started
  routineTimer = new util.CountdownTimer();  // to track time remaining of each (non-slip) routine
  
  return Scheduler.Event.NEXT;
}


var t;
var frameN;
var continueRoutine;
var routineForceEnded;
var trialMaxDurationReached;
var trialMaxDuration;
var trialComponents;
function trialRoutineBegin(snapshot) {
  return async function () {
    TrialHandler.fromSnapshot(snapshot); // ensure that .thisN vals are up to date
    
    //--- Prepare to start Routine 'trial' ---
    t = 0;
    frameN = -1;
    continueRoutine = true; // until we're told otherwise
    // keep track of whether this Routine was forcibly ended
    routineForceEnded = false;
    trialClock.reset();
    routineTimer.reset();
    trialMaxDurationReached = false;
    // update component parameters for each repeat
    rating_time_long.reset()
    psychoJS.experiment.addData('trial.started', globalClock.getTime());
    trialMaxDuration = null
    // keep track of which components have finished
    trialComponents = [];
    trialComponents.push(question_text);
    trialComponents.push(rating_time_long);
    trialComponents.push(label_left);
    trialComponents.push(label_right);
    
    trialComponents.forEach( function(thisComponent) {
      if ('status' in thisComponent)
        thisComponent.status = PsychoJS.Status.NOT_STARTED;
       });
    return Scheduler.Event.NEXT;
  }
}


function trialRoutineEachFrame() {
  return async function () {
    //--- Loop for each frame of Routine 'trial' ---
    // get current time
    t = trialClock.getTime();
    frameN = frameN + 1;// number of completed frames (so 0 is the first frame)
    // update/draw components on each frame
    
    // *question_text* updates
    if (t >= 0.0 && question_text.status === PsychoJS.Status.NOT_STARTED) {
      // keep track of start time/frame for later
      question_text.tStart = t;  // (not accounting for frame time here)
      question_text.frameNStart = frameN;  // exact frame index
      
      question_text.setAutoDraw(true);
    }
    
    
    // if question_text is active this frame...
    if (question_text.status === PsychoJS.Status.STARTED) {
    }
    
    
    // *rating_time_long* updates
    if (t >= 0.0 && rating_time_long.status === PsychoJS.Status.NOT_STARTED) {
      // keep track of start time/frame for later
      rating_time_long.tStart = t;  // (not accounting for frame time here)
      rating_time_long.frameNStart = frameN;  // exact frame index
      
      rating_time_long.setAutoDraw(true);
    }
    
    
    // if rating_time_long is active this frame...
    if (rating_time_long.status === PsychoJS.Status.STARTED) {
    }
    
    
    // Check rating_time_long for response to end Routine
    if (rating_time_long.getRating() !== undefined && rating_time_long.status === PsychoJS.Status.STARTED) {
      continueRoutine = false; }
    
    // *label_left* updates
    if (t >= 0.0 && label_left.status === PsychoJS.Status.NOT_STARTED) {
      // keep track of start time/frame for later
      label_left.tStart = t;  // (not accounting for frame time here)
      label_left.frameNStart = frameN;  // exact frame index
      
      label_left.setAutoDraw(true);
    }
    
    
    // if label_left is active this frame...
    if (label_left.status === PsychoJS.Status.STARTED) {
    }
    
    
    // *label_right* updates
    if (t >= 0.0 && label_right.status === PsychoJS.Status.NOT_STARTED) {
      // keep track of start time/frame for later
      label_right.tStart = t;  // (not accounting for frame time here)
      label_right.frameNStart = frameN;  // exact frame index
      
      label_right.setAutoDraw(true);
    }
    
    
    // if label_right is active this frame...
    if (label_right.status === PsychoJS.Status.STARTED) {
    }
    
    // check for quit (typically the Esc key)
    if (psychoJS.experiment.experimentEnded || psychoJS.eventManager.getKeys({keyList:['escape']}).length > 0) {
      return quitPsychoJS('The [Escape] key was pressed. Goodbye!', false);
    }
    
    // check if the Routine should terminate
    if (!continueRoutine) {  // a component has requested a forced-end of Routine
      routineForceEnded = true;
      return Scheduler.Event.NEXT;
    }
    
    continueRoutine = false;  // reverts to True if at least one component still running
    trialComponents.forEach( function(thisComponent) {
      if ('status' in thisComponent && thisComponent.status !== PsychoJS.Status.FINISHED) {
        continueRoutine = true;
      }
    });
    
    // refresh the screen if continuing
    if (continueRoutine) {
      return Scheduler.Event.FLIP_REPEAT;
    } else {
      return Scheduler.Event.NEXT;
    }
  };
}


function trialRoutineEnd(snapshot) {
  return async function () {
    //--- Ending Routine 'trial' ---
    trialComponents.forEach( function(thisComponent) {
      if (typeof thisComponent.setAutoDraw === 'function') {
        thisComponent.setAutoDraw(false);
      }
    });
    psychoJS.experiment.addData('trial.stopped', globalClock.getTime());
    psychoJS.experiment.addData('rating_time_long.response', rating_time_long.getRating());
    psychoJS.experiment.addData('rating_time_long.rt', rating_time_long.getRT());
    // the Routine "trial" was not non-slip safe, so reset the non-slip timer
    routineTimer.reset();
    
    // Routines running outside a loop should always advance the datafile row
    if (currentLoop === psychoJS.experiment) {
      psychoJS.experiment.nextEntry(snapshot);
    }
    return Scheduler.Event.NEXT;
  }
}


function importConditions(currentLoop) {
  return async function () {
    psychoJS.importAttributes(currentLoop.getCurrentTrial());
    return Scheduler.Event.NEXT;
    };
}


async function quitPsychoJS(message, isCompleted) {
  // Check for and save orphaned data
  if (psychoJS.experiment.isEntryEmpty()) {
    psychoJS.experiment.nextEntry();
  }
  psychoJS.window.close();
  psychoJS.quit({message: message, isCompleted: isCompleted});
  
  return Scheduler.Event.QUIT;
}
