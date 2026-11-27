'use client';
import Link from 'next/link';
import {useEffect, useState} from 'react';
import PortalShell from '../../../components/PortalShell';
import {api, list} from '../../../lib/api';
import type {ProctoredSessionItem} from '../../../lib/api';

function band(score: number) {
  if (score >= 60) return 'High';
  if (score >= 30) return 'Medium';
  return 'Low';
}

export default function ProctoringList() {
  const [sessions, setSessions] = useState<ProctoredSessionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api('/proctoring/')
      .then(data => setSessions(list(data) as ProctoredSessionItem[]))
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load exam sessions.'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PortalShell title="Exam monitoring" role="Instructor" eyebrow="Fair exams">
      <div className="panel">
        <div className="panel-head">
          <div>
            <h2>Monitored exam sessions</h2>
            <p className="muted">
              Camera monitoring only saves short alerts — no video is recorded. The risk score
              never fails an exam; 60+ only flags a session for your review. Low 0–29 · Medium 30–59 · High 60+.
            </p>
          </div>
        </div>
        {error && <div className="form-error" role="alert">{error}</div>}
        {loading ? <p className="muted" aria-live="polite">Loading sessions…</p> : sessions.length === 0 ? (
          <p className="muted">No monitored exam sessions yet.</p>
        ) : sessions.map(session => (
          <div className="problem-row" key={session.id}>
            <div>
              <h3>{session.quiz_title}</h3>
              <small className="muted">
                {session.learner_name} · {session.course_title} · {session.status} · {session.event_count} alerts · {new Date(session.started_at).toLocaleString()}
              </small>
            </div>
            <span>
              <span className="muted">Risk {session.risk_score} ({band(session.risk_score)})</span>{' '}
              <Link className="btn btn-soft" href={`/instructor/proctoring/${session.id}`}>Review</Link>
            </span>
          </div>
        ))}
      </div>
    </PortalShell>
  );
}
