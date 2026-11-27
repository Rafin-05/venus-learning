'use client';
import Link from 'next/link';
import {useParams} from 'next/navigation';
import {useEffect, useState} from 'react';
import PortalShell from '../../../../components/PortalShell';
import {api, post} from '../../../../lib/api';
import type {ProctoredSessionItem} from '../../../../lib/api';

function band(score: number) {
  if (score >= 60) return 'High';
  if (score >= 30) return 'Medium';
  return 'Low';
}

export default function ProctoringDetail() {
  const {id} = useParams<{id: string}>();
  const [session, setSession] = useState<ProctoredSessionItem | null>(null);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  function load() {
    setLoading(true);
    api<ProctoredSessionItem>(`/proctoring/${id}/`)
      .then(value => { setSession(value); setNote(value.review_note || ''); })
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load this session.'))
      .finally(() => setLoading(false));
  }

  useEffect(load, [id]);

  async function review() {
    if (!session) return;
    setSaving(true);
    setError('');
    try {
      const updated = await post<ProctoredSessionItem>(`/proctoring/${session.id}/review/`, {review_note: note});
      setSession(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save the review.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <PortalShell title="Exam session review" role="Instructor" eyebrow="Fair exams">
      {error && <div className="form-error" role="alert">{error}</div>}
      {loading ? <p className="muted" aria-live="polite">Loading session…</p> : !session ? (
        <p className="muted">This session could not be found.</p>
      ) : (
        <>
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>{session.quiz_title}</h2>
                <p className="muted">
                  {session.learner_name} · {session.course_title} · {session.status} · started {new Date(session.started_at).toLocaleString()}
                  {session.ended_at ? ` · ended ${new Date(session.ended_at).toLocaleString()}` : ''}
                </p>
              </div>
              <span><b>Risk {session.risk_score} ({band(session.risk_score)})</b></span>
            </div>
            <p className="muted">
              No video was recorded for this session — only the alert events below. The score is a
              review flag: it never changed the learner&apos;s quiz result.
            </p>
          </div>
          <div className="panel">
            <h2>Event timeline ({session.event_count})</h2>
            {session.events.length === 0 ? <p className="muted">No alerts were recorded.</p> : session.events.map(event => (
              <div className="problem-row" key={event.id}>
                <div>
                  <h3>{event.event_type}</h3>
                  <small className="muted">{new Date(event.created_at).toLocaleString()} · severity {event.severity}</small>
                </div>
              </div>
            ))}
          </div>
          <div className="panel">
            <h2>Review</h2>
            {session.status === 'active' ? (
              <p className="muted">This session is still active. It can be reviewed once the learner ends the exam.</p>
            ) : (
              <>
                <div className="field">
                  <label htmlFor="review-note">Review note</label>
                  <textarea id="review-note" rows={3} value={note} onChange={e => setNote(e.target.value)} />
                </div>
                <button className="btn btn-primary" disabled={saving} onClick={() => void review()}>
                  {saving ? 'Saving…' : session.status === 'reviewed' ? 'Update review' : 'Mark as reviewed'}
                </button>
                {session.status === 'reviewed' && <p className="muted">Reviewed{session.reviewed_at ? ` on ${new Date(session.reviewed_at).toLocaleString()}` : ''}.</p>}
              </>
            )}
            <p style={{marginTop: 12}}><Link href="/instructor/proctoring">← Back to all sessions</Link></p>
          </div>
        </>
      )}
    </PortalShell>
  );
}
