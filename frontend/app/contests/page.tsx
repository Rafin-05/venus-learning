'use client';

import Link from 'next/link';
import {useCallback, useEffect, useState} from 'react';
import PortalShell from '../../components/PortalShell';
import {api, list} from '../../lib/api';
import {LearnerError, LearnerEmpty, LearnerLoading} from '../../components/LearnerStates';

type Contest = {id: number; title: string; description: string; starts_at: string; ends_at: string; prize?: string};
export default function Contests() { const [items, setItems] = useState<Contest[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const load = useCallback(async () => { setLoading(true); try { setItems(list(await api('/contests/'))); } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load contests.'); } finally { setLoading(false); } }, []); useEffect(() => { load(); }, [load]); return <PortalShell title="Challenges & contests" eyebrow="Put your skills to work"><div className="panel"><div className="panel-head"><h2>Available contests</h2><Link href="/leaderboard">Leaderboard →</Link></div>{loading ? <LearnerLoading label="Loading contests…"/> : error ? <LearnerError message={error} retry={load}/> : items.length ? items.map(contest => <div className="problem-row" key={contest.id}><div><h3>{contest.title}</h3><small className="muted">{new Date(contest.starts_at).toLocaleString()} – {new Date(contest.ends_at).toLocaleString()}</small><p className="muted">{contest.description}</p></div><Link className="btn btn-soft" href={`/contests/${contest.id}`}>View contest</Link></div>) : <LearnerEmpty>No contests are scheduled yet.</LearnerEmpty>}</div></PortalShell>; }
