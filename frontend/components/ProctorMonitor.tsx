'use client';
import {useEffect, useRef, useState} from 'react';
import {post} from '../lib/api';

/**
 * Exam monitoring (AI proctoring v1) — camera only during the exam.
 *
 * What it does: after the learner gives explicit consent, it opens the
 * camera (small preview), watches for simple signals, and reports short
 * alert EVENTS to /api/proctoring/<id>/events/ — e.g. "no face visible",
 * "tab hidden", "copy attempted". Only those events are saved.
 *
 * What it does NOT do: no video is recorded, uploaded, or stored; no
 * audio is captured; nothing is analysed on a server. Face presence
 * uses the browser's built-in FaceDetector when the browser has one
 * (Chromium); in other browsers the face check is honestly reported as
 * unavailable and only the tab / camera / copy checks run.
 * The risk score never fails or submits an exam — it only flags the
 * session for instructor review.
 */

type FaceDetectorCtor = new (opts?: {fastMode?: boolean; maxDetectedFaces?: number}) => {
  detect(input: HTMLVideoElement): Promise<{boundingBox: unknown}[]>;
};
declare global {
  interface Window {
    FaceDetector?: FaceDetectorCtor;
  }
}

type Session = {id: number; risk_score: number; risk_band: string; status: string};

type Props = {
  quizId: number;
  /** Parent sets this true (e.g. after the quiz is submitted) to stop monitoring. */
  stopped: boolean;
  onSessionChange: (session: Session | null) => void;
  /** (monitoringActive, cameraBlocked) — the exam page locks the questions while blocked. */
  onMonitoringChange: (active: boolean, blocked: boolean) => void;
};

type Stage = 'consent' | 'starting' | 'active' | 'blocked' | 'ended';

const SEND_GAP_MS = 5000; // at most one event of each type per 5 seconds
const FACE_CHECK_MS = 2000;

export default function ProctorMonitor({quizId, stopped, onSessionChange, onMonitoringChange}: Props) {
  const [stage, setStage] = useState<Stage>('consent');
  const [session, setSession] = useState<Session | null>(null);
  const [faceCheck, setFaceCheck] = useState<'checking' | 'on' | 'unavailable'>('checking');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const detectorRef = useRef<{detect(input: HTMLVideoElement): Promise<{boundingBox: unknown}[]>} | null>(null);
  const lastSentRef = useRef<Record<string, number>>({});
  const sessionRef = useRef<Session | null>(null);
  const endedRef = useRef(false);

  function stopCamera() {
    streamRef.current?.getTracks().forEach(track => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }

  async function sendEvent(eventType: string, detail: Record<string, unknown> = {}) {
    const current = sessionRef.current;
    if (!current) return;
    const now = Date.now();
    if (now - (lastSentRef.current[eventType] || 0) < SEND_GAP_MS) return;
    lastSentRef.current[eventType] = now;
    try {
      const updated = await post<Session>(`/proctoring/${current.id}/events/`, {
        events: [{event_type: eventType, detail}],
      });
      setSession(updated);
      sessionRef.current = updated;
    } catch {
      setNotice('Monitoring events could not be sent. Check your connection — the exam continues.');
    }
  }

  async function startCamera(): Promise<boolean> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {width: {ideal: 640}, height: {ideal: 480}},
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      return true;
    } catch {
      return false;
    }
  }

  async function startMonitoring() {
    setError('');
    setStage('starting');
    let created: Session;
    try {
      created = await post<Session>('/proctoring/', {quiz: quizId, consent_given: true});
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the monitored session.');
      setStage('consent');
      return;
    }
    setSession(created);
    sessionRef.current = created;
    onSessionChange(created);
    const cameraOk = await startCamera();
    if (!cameraOk) {
      // Do NOT silently proceed unmonitored: record it and block the exam
      // until the camera works.
      await sendEvent('CAMERA_BLOCKED', {reason: 'permission-denied-or-unavailable'});
      setStage('blocked');
      onMonitoringChange(false, true);
      return;
    }
    if (typeof window !== 'undefined' && window.FaceDetector) {
      try {
        detectorRef.current = new window.FaceDetector({fastMode: true, maxDetectedFaces: 3});
        setFaceCheck('on');
      } catch {
        setFaceCheck('unavailable');
      }
    } else {
      setFaceCheck('unavailable');
    }
    setStage('active');
    onMonitoringChange(true, false);
  }

  async function retryCamera() {
    setError('');
    const cameraOk = await startCamera();
    if (!cameraOk) {
      setError('The camera is still unavailable. Allow camera access for this site, then try again.');
      return;
    }
    if (typeof window !== 'undefined' && window.FaceDetector && !detectorRef.current) {
      try {
        detectorRef.current = new window.FaceDetector({fastMode: true, maxDetectedFaces: 3});
        setFaceCheck('on');
      } catch { /* Face check stays unavailable; other checks still run. */ }
    }
    setStage('active');
    onMonitoringChange(true, false);
  }

  // Stop monitoring when the parent asks (e.g. quiz submitted).
  useEffect(() => {
    if (!stopped || endedRef.current || !sessionRef.current) return;
    endedRef.current = true;
    const current = sessionRef.current;
    stopCamera();
    post<Session>(`/proctoring/${current.id}/end/`, {}).catch(() => undefined);
    setStage('ended');
    onMonitoringChange(false, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stopped]);

  // Signal checks while monitoring is active.
  useEffect(() => {
    if (stage !== 'active') return;
    const onVisibility = () => {
      if (document.hidden) void sendEvent('TAB_SWITCH', {reason: 'tab-hidden'});
    };
    const onBlur = () => void sendEvent('TAB_SWITCH', {reason: 'window-blur'});
    const onCopy = (event: Event) => {
      event.preventDefault();
      void sendEvent('COPY_ATTEMPT', {kind: event.type});
    };
    const onFullscreen = () => {
      if (!document.fullscreenElement) void sendEvent('FULLSCREEN_EXIT', {});
    };
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('blur', onBlur);
    document.addEventListener('copy', onCopy);
    document.addEventListener('cut', onCopy);
    document.addEventListener('paste', onCopy);
    document.addEventListener('fullscreenchange', onFullscreen);
    const faceTimer = window.setInterval(async () => {
      const detector = detectorRef.current;
      const video = videoRef.current;
      if (!detector || !video || video.readyState < 2) return;
      try {
        const faces = await detector.detect(video);
        if (faces.length === 0) await sendEvent('NO_FACE', {faces: 0});
        else if (faces.length > 1) await sendEvent('MULTIPLE_FACES', {faces: faces.length});
      } catch { /* One failed frame is not an event. */ }
    }, FACE_CHECK_MS);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('blur', onBlur);
      document.removeEventListener('copy', onCopy);
      document.removeEventListener('cut', onCopy);
      document.removeEventListener('paste', onCopy);
      document.removeEventListener('fullscreenchange', onFullscreen);
      window.clearInterval(faceTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage]);

  // Always release the camera when this component leaves the page.
  useEffect(() => () => stopCamera(), []);

  if (stage === 'ended') {
    return (
      <div className="panel" role="status">
        <h2>Monitoring ended</h2>
        <p className="muted">The camera is off. Your exam answers were submitted as normal.</p>
      </div>
    );
  }

  if (stage === 'blocked') {
    return (
      <div className="panel" role="alert">
        <h2>Camera blocked — exam paused</h2>
        <p>
          This is a monitored exam, so it cannot continue without a camera. Your
          camera is blocked or permission was denied. No video is recorded — the
          camera is only used to check that one face is visible during the exam.
        </p>
        <p className="muted">Allow camera access for this site in your browser, then try again. If you cannot, contact your instructor.</p>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="btn btn-primary" type="button" onClick={() => void retryCamera()}>Try camera again</button>
      </div>
    );
  }

  if (stage === 'consent' || stage === 'starting') {
    return (
      <div className="panel">
        <h2>Monitored exam</h2>
        <p>This exam is monitored to keep it fair for everyone. Please read this before you start:</p>
        <ul>
          <li>Your camera turns on <b>only during this exam</b> and turns off when you submit or leave.</li>
          <li><b>No video is recorded or stored.</b> The system only saves short alerts, such as “no face visible” or “tab switched”.</li>
          <li>Your answers and score are never changed by monitoring. A high number of alerts only asks your instructor to review the exam.</li>
          <li>Keep your face visible, stay on this tab, and do not copy or paste.</li>
        </ul>
        {error && <p className="form-error" role="alert">{error}</p>}
        <button className="btn btn-primary" type="button" disabled={stage === 'starting'} onClick={() => void startMonitoring()}>
          {stage === 'starting' ? 'Starting…' : 'I agree — turn on my camera and start the exam'}
        </button>
      </div>
    );
  }

  return (
    <div className="panel" aria-live="polite">
      <div className="panel-head">
        <div>
          <h2>Monitoring is on</h2>
          <p className="muted">
            Camera is on for this exam only. No video is recorded — only short alerts are saved.
            {faceCheck === 'unavailable' ? ' Face check is unavailable in this browser; tab, camera, and copy checks still run.' : ''}
          </p>
        </div>
        <span className="muted">Risk score: {session?.risk_score ?? 0} ({session?.risk_band ?? 'low'})</span>
      </div>
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        aria-label="Camera preview for exam monitoring"
        style={{width: 200, height: 150, borderRadius: 12, background: '#111', objectFit: 'cover'}}
      />
      {notice && <p className="form-error" role="alert">{notice}</p>}
    </div>
  );
}
