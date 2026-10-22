'use client';

import Link from 'next/link';
import {useCallback, useEffect, useState} from 'react';
import PortalShell from '../../components/PortalShell';
import {api, list, type Course, type User} from '../../lib/api';
import {LearnerError, LearnerLoading, LearnerEmpty} from '../../components/LearnerStates';

type Enrollment = {id: number; course: Course; progress_percent: number; enrolled_at: string; completed_at?: string | null};

export default function Dashboard() {
  const [user, setUser] = useState<User | null>(null);
  const [enrollments, setEnrollments] = useState<Enrollment[]>([]);
  const [certificateCount, setCertificateCount] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [me, enrolled, certificates] = await Promise.all([api<User>('/auth/me/'), api('/enrollments/'), api('/certificates/')]);
      setUser(me); setEnrollments(list(enrolled)); setCertificateCount(list(certificates).length);
    } catch (e) { setError(e instanceof Error ? e.message : 'Please sign in and try again.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  return <PortalShell title={user ? `Good morning, ${user.full_name || 'learner'}.` : 'Your learning dashboard'} eyebrow="Your learning space">
    {loading ? <LearnerLoading label="Loading your dashboard…"/> : error ? <LearnerError message={error} retry={load}/> : <>
      <div className="statgrid">
        <div className="stat"><span>Courses in progress</span><b>{enrollments.filter(x => !x.completed_at && x.progress_percent < 100).length}</b><small>Based on your enrollments</small></div>
        <div className="stat"><span>Completed courses</span><b>{enrollments.filter(x => x.completed_at || x.progress_percent === 100).length}</b><small>{certificateCount} certificate{certificateCount === 1 ? '' : 's'} issued</small></div>
        <div className="stat"><span>Current streak</span><b>{user?.current_streak ?? 0} day{user?.current_streak === 1 ? '' : 's'}</b><small>Keep learning to build it</small></div>
      </div>
      <div className="dashboard-columns"><div className="panel"><div className="panel-head"><h2>Continue learning</h2><Link href="/my-learning">View all</Link></div>
        {enrollments.filter(x => !x.completed_at && x.progress_percent < 100).slice(0, 4).map((item, index) => <div className="progress-course" key={item.id}><div className="mini-cover" style={{backgroundImage: `url(${item.course.thumbnail || ['/course-1.png','/course-2.png','/hero-cover.png'][index % 3]})`}}/><div className="progress-info"><b>{item.course.title}</b><span>{item.progress_percent}% complete</span><div className="progress"><i style={{width: `${item.progress_percent}%`}}/></div><Link href={`/learning/${item.course.id}`} className="text-link">Continue learning →</Link></div></div>)}
        {!enrollments.some(x => !x.completed_at && x.progress_percent < 100) && <LearnerEmpty><Link href="/courses" className="text-link">Explore courses to start learning →</Link></LearnerEmpty>}
      </div><div className="panel activity"><div className="panel-head"><h2>Account snapshot</h2></div><div className="activity-row"><i>✓</i><span>{enrollments.length} enrollment{enrollments.length === 1 ? '' : 's'}<small>Synced from your account</small></span></div><div className="activity-row"><i>✦</i><span>{certificateCount} certificate{certificateCount === 1 ? '' : 's'}<small>View your achievements</small></span></div><div className="activity-row"><i>↗</i><span><Link href="/profile" className="text-link">Update your profile</Link><small>Keep your learner details current</small></span></div></div></div>
    </>}
  </PortalShell>;
}
