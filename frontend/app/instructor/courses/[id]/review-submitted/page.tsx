'use client';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import PortalShell from '../../../../../components/PortalShell';
import { api } from '../../../../../lib/api';

type Course = { id: number; title: string; status: string };

export default function ReviewSubmitted() {
  const { id } = useParams<{ id: string }>();
  const [c, setC] = useState<Course | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    api<Course>(`/courses/${id}/`)
      .then(setC)
      .catch(e => setError(e instanceof Error ? e.message : 'Unable to load this course.'))
      .finally(() => setLoading(false));
  }, [id]);

  return <PortalShell title="Course submitted" role="Instructor">
    <div className="panel">
      <h2>Sent for admin review</h2>
      {loading && <p className="muted">Loading your course…</p>}
      {error && <div className="form-error" role="alert">{error}</div>}
      {!loading && !error && <>
        <p><b>{c?.title || 'Your course'}</b> has been sent to an administrator for review.</p>
        <p>Status: <b>{c?.status || 'pending'}</b>{c?.status === 'approved'
          ? ' — this course has already been approved and is visible to learners.'
          : ' — learners cannot see it yet.'}</p>
        <ul>
          <li>An administrator can approve it, reject it, or ask for changes.</li>
          <li>If changes are requested, the notes will appear in the review history on the course editor.</li>
          <li>Editing an approved course sends it back for review again.</li>
        </ul>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
          <Link className="btn btn-soft" href={`/instructor/courses/${id}`}>Back to course editor</Link>
          <Link className="btn btn-soft" href="/instructor/courses">My courses</Link>
          <Link className="btn btn-primary" href="/instructor">Instructor dashboard</Link>
        </div>
      </>}
    </div>
  </PortalShell>;
}
