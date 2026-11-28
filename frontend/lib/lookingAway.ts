/**
 * Sustained looking-away (gaze-away) detection for exam monitoring.
 *
 * Pure, dependency-free geometry over MediaPipe FaceLandmarker landmarks
 * (478 points). It runs entirely in the learner's browser: no landmark,
 * image or video ever leaves the device — the caller only sends a short
 * "LOOKING_AWAY" alert event, like every other proctoring event.
 *
 * How it works
 * -------------
 * FaceLandmarker gives an iris centre for each eye (landmarks 468 and
 * 473) and the eye corners. When a learner looks at the exam screen the
 * iris sits near the centre of the eye; when they turn to look at a book
 * or phone beside the screen, the iris moves toward a corner and/or the
 * head turns, which moves the nose tip sideways relative to the face.
 * Three signals are combined (any one is enough):
 *   - horizontal iris offset: iris x vs. the eye-centre x, / eye width
 *   - vertical iris offset:   iris y vs. the eye-centre y, / eye height
 *     (looking down at a book moves the iris down)
 *   - head yaw:               nose-tip x vs. the face-centre x, / face width
 *
 * Thresholds are deliberately conservative (see LOOKING_AWAY_* below) so
 * normal reading — eyes moving across the question text — stays below
 * them. A single frame is never an event: LookingAwayTracker only fires
 * after the learner has looked away continuously for SUSTAINED_MS
 * (5 seconds), so a quick glance down does not trigger it.
 *
 * Landmark indices (MediaPipe FaceLandmarker, 478 points):
 *   left eye iris centre 468, corners 33 (outer) / 133 (inner),
 *   top 159 / bottom 145; right eye iris centre 473, corners 362
 *   (inner) / 263 (outer), top 386 / bottom 374; nose tip 1;
 *   face sides 234 (left) / 454 (right).
 */

export type Landmark = {x: number; y: number; z?: number};

export type GazeAnalysis = {
  lookingAway: boolean;
  /** Machine-readable reason, sent as the event detail (no images). */
  reason: 'facing-screen' | 'gaze-sideways' | 'gaze-down' | 'gaze-up' | 'head-turned';
  /** Average iris offset across both eyes, in eye-widths (signed). */
  horizontalOffset: number;
  /** Average iris offset across both eyes, in eye-heights (signed, + = down). */
  verticalOffset: number;
  /** Nose-tip offset from the face centre, in face-widths (signed). */
  headYaw: number;
};

/** Iris must move more than ~28% of the eye width sideways to count. */
export const LOOKING_AWAY_HORIZONTAL = 0.28;
/** Iris must move more than ~30% of the eye height down to count. */
export const LOOKING_AWAY_DOWN = 0.3;
/** Iris must move more than ~35% of the eye height up to count. */
export const LOOKING_AWAY_UP = 0.35;
/** Nose tip must move more than ~22% of the face width sideways to count. */
export const LOOKING_AWAY_HEAD_YAW = 0.22;
/** Look away continuously for this long before it becomes an event. */
export const LOOKING_AWAY_SUSTAINED_MS = 5000;

const LEFT_IRIS = 468;
const RIGHT_IRIS = 473;
const LEFT_EYE_OUTER = 33;
const LEFT_EYE_INNER = 133;
const LEFT_EYE_TOP = 159;
const LEFT_EYE_BOTTOM = 145;
const RIGHT_EYE_INNER = 362;
const RIGHT_EYE_OUTER = 263;
const RIGHT_EYE_TOP = 386;
const RIGHT_EYE_BOTTOM = 374;
const NOSE_TIP = 1;
const FACE_LEFT = 234;
const FACE_RIGHT = 454;

function midpoint(a: Landmark, b: Landmark): Landmark {
  return {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2};
}

/** Analyse one face's landmarks. Returns null when the data is unusable. */
export function analyseGaze(landmarks: Landmark[] | null | undefined): GazeAnalysis | null {
  if (!landmarks || landmarks.length < 478) return null;
  const at = (i: number): Landmark | null => {
    const p = landmarks[i];
    return p && Number.isFinite(p.x) && Number.isFinite(p.y) ? p : null;
  };
  const leftIris = at(LEFT_IRIS);
  const rightIris = at(RIGHT_IRIS);
  const leftOuter = at(LEFT_EYE_OUTER);
  const leftInner = at(LEFT_EYE_INNER);
  const leftTop = at(LEFT_EYE_TOP);
  const leftBottom = at(LEFT_EYE_BOTTOM);
  const rightInner = at(RIGHT_EYE_INNER);
  const rightOuter = at(RIGHT_EYE_OUTER);
  const rightTop = at(RIGHT_EYE_TOP);
  const rightBottom = at(RIGHT_EYE_BOTTOM);
  const nose = at(NOSE_TIP);
  const faceLeft = at(FACE_LEFT);
  const faceRight = at(FACE_RIGHT);
  if (
    !leftIris || !rightIris || !leftOuter || !leftInner || !leftTop || !leftBottom ||
    !rightInner || !rightOuter || !rightTop || !rightBottom || !nose || !faceLeft || !faceRight
  ) {
    return null;
  }

  // Per-eye iris offset, normalised by that eye's own size so the result
  // does not depend on how close the learner sits to the camera.
  const eyeOffsets: {h: number; v: number}[] = [];
  const eyes = [
    {iris: leftIris, centre: midpoint(leftOuter, leftInner), width: Math.abs(leftOuter.x - leftInner.x), height: Math.abs(leftTop.y - leftBottom.y)},
    {iris: rightIris, centre: midpoint(rightInner, rightOuter), width: Math.abs(rightInner.x - rightOuter.x), height: Math.abs(rightTop.y - rightBottom.y)},
  ];
  for (const eye of eyes) {
    if (eye.width < 0.01 || eye.height < 0.005) return null;
    eyeOffsets.push({
      h: (eye.iris.x - eye.centre.x) / eye.width,
      v: (eye.iris.y - eye.centre.y) / eye.height,
    });
  }
  const horizontalOffset = (eyeOffsets[0].h + eyeOffsets[1].h) / 2;
  const verticalOffset = (eyeOffsets[0].v + eyeOffsets[1].v) / 2;

  // Head yaw: nose tip vs. the centre of the face, normalised by face width.
  const faceWidth = Math.abs(faceRight.x - faceLeft.x);
  if (faceWidth < 0.01) return null;
  const faceCentreX = (faceLeft.x + faceRight.x) / 2;
  const headYaw = (nose.x - faceCentreX) / faceWidth;

  let reason: GazeAnalysis['reason'] = 'facing-screen';
  if (Math.abs(horizontalOffset) > LOOKING_AWAY_HORIZONTAL) reason = 'gaze-sideways';
  else if (verticalOffset > LOOKING_AWAY_DOWN) reason = 'gaze-down';
  else if (verticalOffset < -LOOKING_AWAY_UP) reason = 'gaze-up';
  else if (Math.abs(headYaw) > LOOKING_AWAY_HEAD_YAW) reason = 'head-turned';

  return {
    lookingAway: reason !== 'facing-screen',
    reason,
    horizontalOffset,
    verticalOffset,
    headYaw,
  };
}

/**
 * Turns per-frame gaze readings into one event per sustained episode.
 * Returns true exactly once when the learner has looked away continuously
 * for LOOKING_AWAY_SUSTAINED_MS, and does not fire again until they face
 * the screen again first. Facing the screen resets the timer.
 */
export class LookingAwayTracker {
  private awaySince: number | null = null;
  private flagged = false;

  observe(lookingAway: boolean, nowMs: number): boolean {
    if (!lookingAway) {
      this.awaySince = null;
      this.flagged = false;
      return false;
    }
    if (this.awaySince === null) {
      this.awaySince = nowMs;
      return false;
    }
    if (!this.flagged && nowMs - this.awaySince >= LOOKING_AWAY_SUSTAINED_MS) {
      this.flagged = true;
      return true;
    }
    return false;
  }

  reset(): void {
    this.awaySince = null;
    this.flagged = false;
  }
}
