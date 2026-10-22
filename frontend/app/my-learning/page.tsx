'use client';

import Link from 'next/link';
import {useCallback, useEffect, useMemo, useState} from 'react';
import PortalShell from '../../components/PortalShell';
import {api, list, type Course} from '../../lib/api';
import {LearnerError, LearnerEmpty, LearnerLoading} from '../../components/LearnerStates';

type Enrollment = {id: number; course: Course; progress_percent: number; completed_at?: string | null};
export default function MyLearning() {
  const [items, setItems] = useState<Enrollment[]>([]); const [tab, setTab] = useState<'progress'|'completed'>('progress'); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = useCallback(async () => { setLoading(true); setError(''); try { setItems(list(await api('/enrollments/'))); } catch (e) { setError(e instanceof Error ? e.message : 'Please try again.'); } finally { setLoading(false); } }, []);
  useEffect(() => { load(); }, [load]);
  const shown = useMemo(() => items.filter(x => tab === 'completed' ? Boolean(x.completed_at) || x.progress_percent === 100 : !x.completed_at && x.progress_percent < 100), [items, tab]);
  return <PortalShell title="My learning"><div className="tabs"><button className={tab === 'progress' ? 'active' : ''} onClick={() => setTab('progress')}>In progress ({items.filter(x => !x.completed_at && x.progress_percent < 100).length})</button><button className={tab === 'completed' ? 'active' : ''} onClick={() => setTab('completed')}>Completed ({items.filter(x => Boolean(x.completed_at) || x.progress_percent === 100).length})</button></div>{loading ? <LearnerLoading label="Loading your enrollments…"/> : error ? <LearnerError message={error} retry={load}/> : shown.length ? <div className="learning-list">{shown.map((item, index) => <article className="learning-card" key={item.id}><div className="wide-cover" style={{backgroundImage: `url(${item.course.thumbnail || ['/course-1.png','/course-2.png','/hero-cover.png'][index % 3]})`}}/><div><span className="tag">{tab === 'completed' ? 'Completed' : 'In progress'}</span><h2>{item.course.title}</h2><p className="muted">{item.course.level || 'All levels'} · {item.course.lesson_count ?? '—'} lessons</p><div className="progress"><i style={{width: `${item.progress_percent}%`}}/></div><small>{item.progress_percent}% complete</small><br/><Link className="btn btn-primary" href={`/learning/${item.course.id}`}>{tab === 'completed' ? 'Review course' : 'Continue learning'}</Link></div></article>)}</div> : <LearnerEmpty>{tab === 'completed' ? 'You have not completed a course yet.' : <span>No active enrollments. <Link href="/courses" className="text-link">Explore courses →</Link></span>}</LearnerEmpty>}</PortalShell>;
}
