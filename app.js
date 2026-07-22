// ============================================================================
// STATUS OF THIS FILE (see chat history for the full investigation):
//
// - Heart Rate (standard 0x180D/0x2A37): fully understood, decoded for real.
// - 0xF0F0 (documented Suunto/Movesense raw-motion channel): we requested a
//   fast accelerometer stream from it and empirically found that one byte
//   position in the fast stream rises and falls in a rhythm that closely
//   matches real footstep counts (validated against controlled step tests).
//   That's used below for a *derived, experimental* cadence estimate.
// - 0xFDF3 (Darefore's own private/undocumented channel): this is where the
//   real, finished running-dynamics numbers (GCT, vertical oscillation,
//   stride length, precise lean/balance) almost certainly live, but we have
//   not been able to unlock it — it accepts writes silently but never
//   responds. Until we get Darefore's protocol docs/code, those fields stay
//   as "—" here rather than showing made-up numbers.
// ============================================================================

const DEVICE_NAME_FILTER = 'Darefore';

const HR_SERVICE = 'heart_rate';
const HR_MEASUREMENT = 0x2a37;

const FDF3_SERVICE = '0000fdf3-0000-1000-8000-00805f9b34fb';
const FDF3_NOTIFY = '6b200002-ff4e-4979-8186-fb7ba486fcd7';
const FDF3_WRITE = '6b200001-ff4e-4979-8186-fb7ba486fcd7';

const F0F0_SERVICE = '0000f0f0-0000-1000-8000-00805f9b34fb';
const F0F0_NOTIFY = '34800002-7185-4d5d-b431-630e7050e8f0';
const F0F0_WRITE = '34800001-7185-4d5d-b431-630e7050e8f0';

const KNOWN_SERVICE_UUIDS = [HR_SERVICE, FDF3_SERVICE, F0F0_SERVICE];

// Command requesting an accelerometer stream from the Movesense-style
// protocol on 0xF0F0: [SUBSCRIBE=0x01][reference byte][ASCII resource path].
// There is only ONE message format here (confirmed by checking captures from
// both "/Meas/Acc/13" and "/Meas/Acc" -- both decode to the same real-unit
// (m/s^2) XYZ acceleration floats). Cadence and lean are just two different
// interpretations of that same message, decoded together below -- no need to
// tell messages apart by shape.
const F0F0_SUBSCRIBE_ACCEL = new Uint8Array([
  0x01, 0x05, ...toAsciiBytes('/Meas/Acc'),
]);
const F0F0_DEFAULT_REFERENCE = 0x02;

const metrics = {
  hr: null,    // beats per minute (real, decoded from standard Heart Rate service)
  cad: null,   // steps per minute (experimental, derived from raw motion)
  gct: null,   // ground contact time, ms (experimental, derived from raw motion)
  vo: null,    // vertical oscillation, cm -- needs 0xFDF3 (double-integration drift made this unreliable)
  speed: null, // m/s (experimental, derived from raw motion, rough calibration)
  sl: null,    // stride length, mm (derived: speed / (cadence/60), no new sensor analysis needed)
  lean: null,  // degrees, signed -- needs 0xFDF3
  bal: null,   // left/right balance, % (experimental; sides are consistent, not confirmed L vs R)
};

let device = null;
let server = null;

const statusEl = document.getElementById('status');
const logEl = document.getElementById('log');
const rawLogEl = document.getElementById('rawLog');
const connectBtn = document.getElementById('connectBtn');
const resetLeanBtn = document.getElementById('resetLeanBtn');
const clearBtn = document.getElementById('clearBtn');
const downloadBtn = document.getElementById('downloadBtn');
const recordDurationSelect = document.getElementById('recordDurationSelect');
const timedRecordBtn = document.getElementById('timedRecordBtn');
const rawToggle = document.getElementById('rawToggle');
const displayRateSelect = document.getElementById('displayRateSelect');

let displayIntervalMs = Number(displayRateSelect.value);
let lastDisplayMs = -Infinity;

displayRateSelect.addEventListener('change', () => {
  displayIntervalMs = Number(displayRateSelect.value);
});

rawToggle.addEventListener('change', () => {
  rawLogEl.classList.toggle('hidden', !rawToggle.checked);
});

// Recorded at full decode rate, independent of the display throttle above --
// slowing down what's shown on screen shouldn't cost you resolution in the
// exported data.
const RECORDED_COLUMNS = ['datetime', 't_ms', 'hr', 'cad', 'gct', 'vo', 'speed', 'sl', 'lean', 'bal'];
let recordedRows = [];
let recordStartMs = null;

function recordRow(m) {
  const now = Date.now();
  if (recordStartMs === null) recordStartMs = now;
  recordedRows.push({ datetime: formatTimestamp(new Date(now)), t_ms: now - recordStartMs, ...m });
}

clearBtn.addEventListener('click', () => {
  logEl.textContent = '';
  rawLogEl.textContent = '';
  recordedRows = [];
  recordStartMs = null;
});

function downloadCsv() {
  if (recordedRows.length === 0) {
    setStatus('nothing recorded yet -- connect and collect some data first');
    return;
  }
  const lines = [RECORDED_COLUMNS.join(',')];
  for (const row of recordedRows) {
    lines.push(RECORDED_COLUMNS.map((col) => (row[col] ?? '')).join(','));
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `darefore-data-${new Date().toISOString().replace(/[:.]/g, '-')}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

downloadBtn.addEventListener('click', downloadCsv);

// Timed recording: clears any existing recording, then auto-stops and
// auto-downloads once the chosen duration elapses -- recordRow() itself
// still records unconditionally, so this just bookends a clean window and
// saves having to babysit the clock and click Download at the right moment.
let timedRecordEndMs = null;
let timedRecordIntervalId = null;

function stopTimedRecording(shouldDownload) {
  clearInterval(timedRecordIntervalId);
  timedRecordIntervalId = null;
  timedRecordEndMs = null;
  timedRecordBtn.textContent = 'Start Timed Recording';
  if (shouldDownload) downloadCsv();
}

timedRecordBtn.addEventListener('click', () => {
  if (timedRecordEndMs !== null) {
    stopTimedRecording(false);
    setStatus('timed recording cancelled');
    return;
  }

  const durationSec = Number(recordDurationSelect.value);
  recordedRows = [];
  recordStartMs = null;
  timedRecordEndMs = Date.now() + durationSec * 1000;
  timedRecordBtn.textContent = `Recording… ${durationSec}s left (click to cancel)`;
  timedRecordIntervalId = setInterval(() => {
    const remainingMs = timedRecordEndMs - Date.now();
    if (remainingMs <= 0) {
      stopTimedRecording(true);
      setStatus('timed recording complete -- CSV downloaded');
      return;
    }
    timedRecordBtn.textContent = `Recording… ${Math.ceil(remainingMs / 1000)}s left (click to cancel)`;
  }, 250);
});

connectBtn.addEventListener('click', connect);
resetLeanBtn.addEventListener('click', resetLeanBaseline);

async function connect() {
  try {
    setStatus('requesting device…');
    device = await navigator.bluetooth.requestDevice({
      filters: [{ namePrefix: DEVICE_NAME_FILTER }],
      optionalServices: KNOWN_SERVICE_UUIDS,
    });

    device.addEventListener('gattserverdisconnected', onDisconnected);

    setStatus(`connecting to ${device.name || device.id}…`);
    server = await device.gatt.connect();

    let subscribed = 0;
    for (const serviceUuid of KNOWN_SERVICE_UUIDS) {
      const service = await server.getPrimaryService(serviceUuid);
      const characteristics = await service.getCharacteristics();
      for (const characteristic of characteristics) {
        if (characteristic.properties.notify || characteristic.properties.indicate) {
          characteristic.addEventListener('characteristicvaluechanged', onNotification);
          await characteristic.startNotifications();
          subscribed++;
        }
      }
    }

    // Ask 0xF0F0 for its accelerometer stream (feeds both cadence and lean).
    try {
      const f0f0Service = await server.getPrimaryService(F0F0_SERVICE);
      const writeChar = await f0f0Service.getCharacteristic(F0F0_WRITE);
      await writeChar.writeValue(F0F0_SUBSCRIBE_ACCEL);
    } catch (err) {
      console.warn('Could not request accelerometer streams from 0xF0F0:', err);
    }

    setStatus(`connected to ${device.name || device.id} — subscribed to ${subscribed} characteristic(s)`);
  } catch (err) {
    setStatus(`error: ${err.message}`);
    console.error(err);
  }
}

function onDisconnected() {
  setStatus('disconnected');
}

function onNotification(event) {
  const characteristic = event.target;
  const dataView = characteristic.value;

  // Decoding always runs on every notification -- the detection algorithms
  // (cadence, GCT, balance, lean) need every raw sample to work correctly.
  // Only the on-screen log is throttled, so slowing it down can't affect
  // the underlying data quality.
  const updates = decode(characteristic.uuid, dataView);
  Object.assign(metrics, updates);
  recordRow(metrics);

  const now = Date.now();
  if (now - lastDisplayMs < displayIntervalMs) return;
  lastDisplayMs = now;

  if (rawToggle.checked) {
    appendRaw(characteristic.uuid, dataView);
  }
  appendRow(metrics);
}

// ============================================================================
// Decoding
// ============================================================================
function decode(characteristicUuid, dataView) {
  if (matchesUuid(characteristicUuid, HR_MEASUREMENT)) {
    return decodeHeartRate(dataView);
  }
  if (characteristicUuid === F0F0_NOTIFY) {
    return decodeF0F0(dataView);
  }
  // characteristicUuid === FDF3_NOTIFY would go here once we know its format.
  return {};
}

function matchesUuid(uuid, shortForm16bit) {
  const expected = `0000${shortForm16bit.toString(16).padStart(4, '0')}-0000-1000-8000-00805f9b34fb`;
  return uuid === expected;
}

function decodeHeartRate(dv) {
  const flags = readUInt8(dv, 0);
  const hrIsUint16 = (flags & 0x01) !== 0;
  const bpm = hrIsUint16 ? readUInt16LE(dv, 1) : readUInt8(dv, 1);
  return { hr: bpm };
}

// --- experimental cadence extraction from the 0xF0F0 fast accelerometer stream ---
//
// Validated against real captures: byte 9 toggles between two distinct levels
// (like a switch) once per step while walking/running, and sits rock-steady
// when truly motionless. So instead of hunting for "peaks", we count how many
// times it commits to "high" after having clearly settled at "low" (a rising
// edge with hysteresis, like a Schmitt trigger) -- this matched a real
// counted 66-step walk almost exactly. Hysteresis (a gap between the "count
// this as low" and "count this as high" thresholds, instead of one midline)
// is what keeps small wobbles/twists from being mistaken for steps, and stops
// sensor noise right at the midpoint from double-counting a single step.
const CADENCE_BYTE_OFFSET = 9;
const MIN_ABSOLUTE_RANGE = 40;   // below this, treat as "not moving" noise, not real steps
const HYSTERESIS_FRACTION = 0.25; // half-width of the dead zone, as a fraction of the range
const REFRACTORY_MS = 250;       // minimum time between counted steps (caps ~240 spm)
const STALE_MS = 1500;           // no new step counted in this long -> report stopped (0)
const CROSSING_WINDOW_MS = 8000; // how far back to look when averaging step rate
const RANGE_WINDOW = 60;         // samples used to compute the dynamic threshold
const MIN_CROSSINGS_TO_REPORT = 3; // require a sustained rhythm, not a one-off movement
const MAX_INTERVAL_DEVIATION_FRACTION = 0.4; // recent step intervals must be this evenly spaced

let rawBuffer = [];
let hysteresisState = null; // 'low' | 'high' | null (unknown yet)
let lastCrossingMs = -Infinity;
let crossingTimestamps = [];

function decodeF0F0(dv) {
  const bytes = new Uint8Array(dv.buffer, dv.byteOffset, dv.byteLength);
  if (bytes.length < CADENCE_BYTE_OFFSET + 1) return {};

  const referenceByte = bytes[1];
  if (referenceByte === F0F0_DEFAULT_REFERENCE) {
    // slow default stream — not the one we derived cadence from
    return {};
  }

  const leanUpdate = bytes.length >= 18 ? decodeLeanFromRawAccel(dv) : {};
  const gctUpdate = bytes.length >= 18 ? decodeGctFromRawAccel(dv, Date.now()) : {};
  const speedUpdate = bytes.length >= 18 ? decodeSpeedFromRawAccel(dv, Date.now()) : {};
  const balanceUpdate = bytes.length >= 18 ? decodeBalanceFromRawAccel(dv, Date.now()) : {};

  const raw = bytes[CADENCE_BYTE_OFFSET];
  rawBuffer.push(raw);
  if (rawBuffer.length > RANGE_WINDOW) rawBuffer.shift();

  const recentMin = Math.min(...rawBuffer);
  const recentMax = Math.max(...rawBuffer);
  const range = recentMax - recentMin;
  const now = Date.now();

  if (range >= MIN_ABSOLUTE_RANGE) {
    const mid = (recentMin + recentMax) / 2;
    const margin = range * HYSTERESIS_FRACTION;
    const highThreshold = mid + margin;
    const lowThreshold = mid - margin;

    if (hysteresisState === null) {
      hysteresisState = raw > mid ? 'high' : 'low';
    } else if (hysteresisState === 'low' && raw >= highThreshold) {
      if (now - lastCrossingMs >= REFRACTORY_MS) {
        lastCrossingMs = now;
        crossingTimestamps.push(now);
      }
      hysteresisState = 'high';
    } else if (hysteresisState === 'high' && raw <= lowThreshold) {
      hysteresisState = 'low';
    }
    // values strictly between lowThreshold and highThreshold don't change state --
    // that's the point of the dead zone.
  }

  crossingTimestamps = crossingTimestamps.filter((t) => now - t <= CROSSING_WINDOW_MS);

  // Nothing counted recently -- treat as stopped, and forget old crossings so a
  // resumed walk starts a fresh measurement instead of blending in stale data.
  if (now - lastCrossingMs > STALE_MS) {
    crossingTimestamps = [];
    return { cad: 0, sl: 0, ...leanUpdate, ...gctUpdate, ...speedUpdate, ...balanceUpdate };
  }

  // A single transition (e.g. standing up) shouldn't look like a cadence.
  if (crossingTimestamps.length < MIN_CROSSINGS_TO_REPORT) return { cad: null, sl: null, ...leanUpdate, ...gctUpdate, ...speedUpdate, ...balanceUpdate };

  // A one-off jolt (e.g. an elbow dropping onto an armrest) can make the sensor
  // bounce enough to cross the threshold a few times too -- but that bounce is
  // irregular (fast, then decaying), unlike genuine steady steps. Require the
  // most recent intervals to be evenly spaced before trusting them as real gait.
  const recentCrossings = crossingTimestamps.slice(-4);
  if (recentCrossings.length >= 3) {
    const intervals = [];
    for (let i = 1; i < recentCrossings.length; i++) {
      intervals.push(recentCrossings[i] - recentCrossings[i - 1]);
    }
    const meanInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;
    const maxDeviation = Math.max(...intervals.map((iv) => Math.abs(iv - meanInterval)));
    if (maxDeviation > meanInterval * MAX_INTERVAL_DEVIATION_FRACTION) {
      return { cad: 0, sl: 0, ...leanUpdate, ...gctUpdate, ...speedUpdate, ...balanceUpdate };
    }
  }

  const spanMs = crossingTimestamps[crossingTimestamps.length - 1] - crossingTimestamps[0];
  if (spanMs <= 0) return { cad: null, sl: null, ...leanUpdate, ...gctUpdate, ...speedUpdate, ...balanceUpdate };
  const stepsPerMs = (crossingTimestamps.length - 1) / spanMs;
  const cad = Math.round(stepsPerMs * 60000);
  const sl = computeStrideLengthMm(speedUpdate.speed, cad);
  return { cad, sl, ...leanUpdate, ...gctUpdate, ...speedUpdate, ...balanceUpdate };
}

// stride length (mm) = distance per step = speed / steps-per-second, derived
// arithmetically from the two metrics we already compute -- no new sensor
// analysis needed. Undefined if we don't have a real cadence to divide by.
function computeStrideLengthMm(speedMps, cadSpm) {
  if (speedMps == null || !cadSpm) return null;
  const stepsPerSecond = cadSpm / 60;
  return Math.round((speedMps / stepsPerSecond) * 1000);
}

// --- experimental lean extraction from the 0xF0F0 raw accelerometer stream ---
//
// Validated against a real controlled tilt test: two of the floats in this
// message trade off exactly like two accelerometer axes rotating relative to
// gravity (one shrinks toward zero while the other grows), which is the
// standard physics behind any tilt sensor. We compute the angle between them
// with atan2, then report it relative to whatever orientation the sensor was
// in when it first connected (there's no absolute "0 degrees" without
// Darefore's own calibration, so this is a relative lean, not an absolute one).
const LEAN_AXIS_1_OFFSET = 10;
const LEAN_AXIS_2_OFFSET = 14;
const LEAN_BASELINE_SAMPLES = 20; // averaged together whenever the baseline is (re)calibrated

let leanBaselineDeg = null;
let leanCalibrating = true; // collecting samples toward a new baseline right now
let leanCalibrationSamples = [];

// Angles wrap at +-180 degrees, so a plain arithmetic mean of raw samples
// straddling that wrap (e.g. 179 and -179) would average to ~0 instead of
// ~180. Averaging each sample's sin/cos and taking atan2 of the sums handles
// the wraparound correctly.
function circularMeanDeg(anglesDeg) {
  let sumSin = 0;
  let sumCos = 0;
  for (const deg of anglesDeg) {
    const rad = (deg * Math.PI) / 180;
    sumSin += Math.sin(rad);
    sumCos += Math.cos(rad);
  }
  return (Math.atan2(sumSin, sumCos) * 180) / Math.PI;
}

// Re-arms baseline calibration so the next LEAN_BASELINE_SAMPLES readings
// become the new "zero lean" orientation -- lets the user recenter mid-run
// without disconnecting.
function resetLeanBaseline() {
  leanCalibrating = true;
  leanCalibrationSamples = [];
}

function decodeLeanFromRawAccel(dv) {
  const a1 = dv.getFloat32(LEAN_AXIS_1_OFFSET, true);
  const a2 = dv.getFloat32(LEAN_AXIS_2_OFFSET, true);
  const angleDeg = (Math.atan2(a2, a1) * 180) / Math.PI;

  if (leanCalibrating) {
    leanCalibrationSamples.push(angleDeg);
    if (leanCalibrationSamples.length >= LEAN_BASELINE_SAMPLES) {
      leanBaselineDeg = circularMeanDeg(leanCalibrationSamples);
      leanCalibrating = false;
    }
    return { lean: 0 };
  }

  let lean = angleDeg - leanBaselineDeg;
  // normalize to -180..180 in case we wrapped around
  if (lean > 180) lean -= 360;
  if (lean < -180) lean += 360;
  return { lean };
}

// --- experimental ground contact time extraction from the same raw stream ---
//
// Validated against two real controlled tests: acceleration magnitude spikes
// sharply on impact and drops low during the airborne/swing phase, and timing
// the width of each spike gave median GCT of 297ms (deliberate slow pace,
// matched 22/22 real counted steps) vs 187ms (faster pace, 31/32 steps) --
// shorter ground contact at higher pace is exactly the expected real-world
// relationship, which is about as good a validation as we can get without a
// force plate or slow-motion video to check exact values against.
const GCT_FALLBACK_THRESHOLD = 8.0; // used only when there's not enough recent signal variation to adapt
const GCT_THRESHOLD_FRACTION = 0.4; // where between recent quiet/impact magnitude to draw the line
const GCT_RANGE_WINDOW = 60;        // samples used to compute the dynamic threshold
const GCT_MIN_ABSOLUTE_RANGE = 5;   // below this, fall back to the fixed threshold instead of trusting noise
const GCT_MIN_MS = 80;       // ignore blips shorter than this as noise
const GCT_MAX_MS = 500;      // real GCT is never this long -- reject as a bad detection
const GCT_STALE_MS = 2000;   // no new stance counted in this long -> report unknown
const GCT_HISTORY_SIZE = 5;  // rolling-average window, in stances

let gctInStance = false;
let gctStanceStartMs = null;
let gctHistory = [];
let gctLastStanceEndMs = -Infinity;
let gctMagBuffer = [];

function decodeGctFromRawAccel(dv, nowMs) {
  const ax = dv.getFloat32(6, true);
  const ay = dv.getFloat32(10, true);
  const az = dv.getFloat32(14, true);
  const mag = Math.sqrt(ax * ax + ay * ay + az * az);

  // Dynamic threshold (same idea as cadence's): adapts to whatever quiet/impact
  // range this specific session actually shows -- different strap tightness,
  // running surface, or intensity all shift the real magnitudes involved, so a
  // single hardcoded number tuned to our own test sessions won't generalize as
  // well as recalibrating against recent history.
  gctMagBuffer.push(mag);
  if (gctMagBuffer.length > GCT_RANGE_WINDOW) gctMagBuffer.shift();
  const recentMin = Math.min(...gctMagBuffer);
  const recentMax = Math.max(...gctMagBuffer);
  const threshold = recentMax - recentMin >= GCT_MIN_ABSOLUTE_RANGE
    ? recentMin + (recentMax - recentMin) * GCT_THRESHOLD_FRACTION
    : GCT_FALLBACK_THRESHOLD;

  const above = mag > threshold;
  if (above && !gctInStance) {
    gctInStance = true;
    gctStanceStartMs = nowMs;
  } else if (!above && gctInStance) {
    gctInStance = false;
    const duration = nowMs - gctStanceStartMs;
    if (duration >= GCT_MIN_MS && duration <= GCT_MAX_MS) {
      gctHistory.push(duration);
      if (gctHistory.length > GCT_HISTORY_SIZE) gctHistory.shift();
      gctLastStanceEndMs = nowMs;
    }
  }

  if (nowMs - gctLastStanceEndMs > GCT_STALE_MS) {
    gctHistory = [];
    return { gct: null };
  }

  if (gctHistory.length === 0) return { gct: null };
  const avg = gctHistory.reduce((a, b) => a + b, 0) / gctHistory.length;
  return { gct: Math.round(avg) };
}

// --- experimental speed extraction from the same raw accelerometer stream ---
//
// Validated against two real walks of a known 20ft distance at different
// paces: the raw single-integrated horizontal speed came out consistently
// ~2.9x lower than the true measured speed in BOTH tests (2.89x and 2.96x --
// close enough to trust as a real, if rough, calibration rather than a fluke
// at one pace). Uses its own independent stride-boundary tracking (same
// threshold as GCT) rather than sharing state, to avoid touching the
// already-validated GCT logic.
const SPEED_THRESHOLD = 8.0;
const SPEED_STALE_MS = 2000;
const SPEED_HISTORY_SIZE = 5;
const SPEED_CALIBRATION_FACTOR = 2.9; // empirical, from 2 walking-pace tests -- may not hold at other paces

let speedInStance = false;
let speedLastStanceEndMs = -Infinity;
let speedSegment = []; // {t, h1, h2} samples accumulated during the current stride
let speedHistory = [];

function decodeSpeedFromRawAccel(dv, nowMs) {
  const h1 = dv.getFloat32(6, true);  // "ax" -- horizontal axis
  const ay = dv.getFloat32(10, true); // vertical axis, used only to detect stance
  const h2 = dv.getFloat32(14, true); // "az" -- horizontal axis
  const mag = Math.sqrt(h1 * h1 + ay * ay + h2 * h2);

  const above = mag > SPEED_THRESHOLD;
  if (above && !speedInStance) {
    speedInStance = true;
    // a new stride is starting -- close out and process the previous one
    if (speedSegment.length >= 3) {
      const n = speedSegment.length;
      const h1Mean = speedSegment.reduce((a, s) => a + s.h1, 0) / n;
      const h2Mean = speedSegment.reduce((a, s) => a + s.h2, 0) / n;
      let v1 = 0, v2 = 0, peak = 0, prevT = speedSegment[0].t;
      for (let i = 1; i < n; i++) {
        const s = speedSegment[i];
        const dt = (s.t - prevT) / 1000;
        v1 += (s.h1 - h1Mean) * dt;
        v2 += (s.h2 - h2Mean) * dt;
        peak = Math.max(peak, Math.sqrt(v1 * v1 + v2 * v2));
        prevT = s.t;
      }
      speedHistory.push(peak * SPEED_CALIBRATION_FACTOR);
      if (speedHistory.length > SPEED_HISTORY_SIZE) speedHistory.shift();
      speedLastStanceEndMs = nowMs;
    }
    speedSegment = [];
  } else if (!above && speedInStance) {
    speedInStance = false;
  }
  speedSegment.push({ t: nowMs, h1, h2 });

  if (nowMs - speedLastStanceEndMs > SPEED_STALE_MS) {
    speedHistory = [];
    return { speed: 0 };
  }
  if (speedHistory.length === 0) return { speed: null };
  const avg = speedHistory.reduce((a, b) => a + b, 0) / speedHistory.length;
  return { speed: Math.round(avg * 10) / 10 };
}

// --- experimental balance extraction from the same raw accelerometer stream ---
//
// Validated against real running data: the horizontal "ax" axis's peak value
// during each stride alternates sign cleanly and consistently once gait
// settles into a steady rhythm (17 strides in a row alternated perfectly in
// one test) -- a real biomechanical signature of the body swaying side to
// side with each footstrike. We have no independent way to confirm which
// sign is "true left" vs "true right" (would need a per-foot reference we
// don't have), but for a left/right TIME SPLIT percentage that doesn't
// matter -- only that strides reliably alternate between two groups, and we
// pair that grouping with the already-validated per-stride GCT duration.
const BALANCE_THRESHOLD = 8.0;
const BALANCE_MIN_MS = 80;
const BALANCE_MAX_MS = 500;
const BALANCE_STALE_MS = 2000;
const BALANCE_HISTORY_SIZE = 10; // strides
const BALANCE_MIN_STRIDES = 4;   // wait for a few strides before reporting

let balanceInStance = false;
let balanceStanceStartMs = null;
let balanceSegment = []; // raw ax samples accumulated during the current stride
let balanceHistory = []; // { side: 'A'|'B', duration }
let balanceLastStanceEndMs = -Infinity;

function decodeBalanceFromRawAccel(dv, nowMs) {
  const ax = dv.getFloat32(6, true);
  const ay = dv.getFloat32(10, true);
  const az = dv.getFloat32(14, true);
  const mag = Math.sqrt(ax * ax + ay * ay + az * az);

  const above = mag > BALANCE_THRESHOLD;
  if (above && !balanceInStance) {
    balanceInStance = true;
    if (balanceSegment.length > 0 && balanceStanceStartMs !== null) {
      const duration = nowMs - balanceStanceStartMs;
      // Mean of the whole stride segment instead of a single peak sample --
      // far less sensitive to one noisy reading flipping the classification.
      const mean = balanceSegment.reduce((a, v) => a + v, 0) / balanceSegment.length;
      const side = mean >= 0 ? 'A' : 'B';
      if (duration >= BALANCE_MIN_MS && duration <= BALANCE_MAX_MS) {
        balanceHistory.push({ side, duration });
        if (balanceHistory.length > BALANCE_HISTORY_SIZE) balanceHistory.shift();
        balanceLastStanceEndMs = nowMs;
      }
    }
    balanceStanceStartMs = nowMs;
    balanceSegment = [];
  } else if (!above && balanceInStance) {
    balanceInStance = false;
  }
  balanceSegment.push(ax);

  if (nowMs - balanceLastStanceEndMs > BALANCE_STALE_MS) {
    balanceHistory = [];
    return { bal: null };
  }
  if (balanceHistory.length < BALANCE_MIN_STRIDES) return { bal: null };

  const totalA = balanceHistory.filter((s) => s.side === 'A').reduce((a, s) => a + s.duration, 0);
  const totalB = balanceHistory.filter((s) => s.side === 'B').reduce((a, s) => a + s.duration, 0);
  const total = totalA + totalB;
  if (total === 0) return { bal: null };
  return { bal: Math.round((totalA / total) * 100) };
}

function toAsciiBytes(str) {
  return Array.from(str).map((c) => c.charCodeAt(0));
}

function readUInt8(dv, offset) { return dv.getUint8(offset); }
function readInt8(dv, offset) { return dv.getInt8(offset); }
function readUInt16LE(dv, offset) { return dv.getUint16(offset, true); }
function readInt16LE(dv, offset) { return dv.getInt16(offset, true); }
function readUInt32LE(dv, offset) { return dv.getUint32(offset, true); }
function readFloat32LE(dv, offset) { return dv.getFloat32(offset, true); }

// ============================================================================
// Display
// ============================================================================
function formatValue(value, unit, decimals) {
  if (value === null || value === undefined) return '—' + (unit || '');
  if (decimals !== undefined) return value.toFixed(decimals) + (unit || '');
  return value + (unit || '');
}

function formatTimestamp(date) {
  const pad = (n, len = 2) => String(n).padStart(len, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} `
    + `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${pad(date.getMilliseconds(), 3)}`;
}

function formatSigned(value, decimals) {
  if (value === null || value === undefined) return '—';
  const sign = value >= 0 ? '+' : '';
  return sign + value.toFixed(decimals);
}

function formatRow(m) {
  return [
    `hr ${formatValue(m.hr, ' bpm')}`,
    `cad ${formatValue(m.cad, ' spm')}`,
    `gct ${formatValue(m.gct, ' ms')}`,
    `vo ${formatValue(m.vo, ' cm')}`,
    `${formatValue(m.speed, ' m/s', m.speed != null ? 1 : undefined)}`,
    `SL ${formatValue(m.sl, ' mm')}`,
    `lean ${formatSigned(m.lean, 2)}°`,
    `bal ${formatValue(m.bal)}`,
  ].join(' | ');
}

function appendRow(m) {
  logEl.textContent += `${formatTimestamp(new Date())}  ${formatRow(m)}\n`;
  logEl.scrollTop = logEl.scrollHeight;
  setStatus('connected — cadence is experimental; gct/vo/speed/sl/lean/bal need the still-locked 0xFDF3 channel');
}

function appendRaw(uuid, dataView) {
  const bytes = new Uint8Array(dataView.buffer, dataView.byteOffset, dataView.byteLength);
  const hex = Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join(' ');
  rawLogEl.textContent += `${uuid}  [${bytes.length}B]  ${hex}\n`;
  rawLogEl.scrollTop = rawLogEl.scrollHeight;
}

function setStatus(text) {
  statusEl.textContent = text;
}

if (!navigator.bluetooth) {
  setStatus('Web Bluetooth is not available in this browser. Use Chrome or Edge over HTTPS or localhost.');
  connectBtn.disabled = true;
}
