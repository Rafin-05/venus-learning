'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useState } from 'react';
import PortalShell from '../../../components/PortalShell';
import { api, list, post } from '../../../lib/api';

type Course = { id: number; title: string; status: string; units?: unknown[]; submitted_at?: string | null; latest_review?: { decision: string; notes: string } | null };

function reviewLabel(decision: string): string {
  return decision === 'changes_requested' ? 'Changes requested' : decision === 'approved' ? 'Approved' : decision === 'rejected' ? 'Rejected' : 'Submitted';
}

function reviewNote(course: Course): string {
  const review = course.latest_review;
  if (!review) return '';
  return review.notes ? ` \u00b7 ${reviewLabel(review.decision)}: ${review.notes}` : ` \u00b7 ${reviewLabel(review.decision)}`;
}

export default function Courses() {
  const router = useRouter();
  const [courses, setCourses] = useState<Course[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<number | null>(null);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try { setCourses(list(await api('/courses/?mine=1'))); }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to load your courses.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  async function submit(id: number) {
    setBusyId(id); setError('');
    try { await post(`/courses/${id}/submit-review/`, {}); router.push(`/instructor/courses/${id}/review-submitted`); }
    catch (e) { setError(e instanceof Error ? e.message : 'Unable to submit this course.'); }
    finally { setBusyId(null); }
  }
  return <PortalShell title="My courses" role="Instructor"><div className="panel">
    <div className="panel-head"><div><h2>Course workspace</h2><p className="muted">Draft, structure and submit courses for staff approval.</p></div><Link className="btn btn-primary" href="/instructor/courses/new">+ Create course</Link></div>
    {error && <div className="form-error" role="alert">{error}</div>}
    {loading && <p className="muted">Loading your courses…</p>}
    {!loading && courses.length === 0 && <p className="muted">You have not created a course yet.</p>}
    {courses.map(course => <div className="problem-row" key={course.id}><div><h3>{course.title}</h3><small className="muted">{course.status} · {course.units?.length ?? 0} units{course.status === 'pending' && course.submitted_at ? ` · Submitted ${new Date(course.submitted_at).toLocaleDateString()}` : ''}{reviewNote(course)}</small></div><span><Link className="btn btn-soft" href={`/instructor/courses/${course.id}`}>Edit curriculum</Link>{course.status !== 'pending' && course.status !== 'approved' && <button className="btn btn-primary" disabled={busyId === course.id} onClick={() => void submit(course.id)}>{busyId === course.id ? 'Submitting…' : 'Submit for review'}</button>}</span></div>)}
  </div></PortalShell>;
}
