'use client';

import Link from 'next/link';
import {useCallback, useEffect, useState} from 'react';
import PortalShell from '../../components/PortalShell';
import {api, list} from '../../lib/api';
import {LearnerError, LearnerEmpty, LearnerLoading} from '../../components/LearnerStates';

type Problem = {id: number; title: string; statement: string; input_format?: string; output_format?: string};
export default function Problems() { const [items, setItems] = useState<Problem[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const load = useCallback(async () => { setLoading(true); try { setItems(list(await api('/problems/'))); } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load problems.'); } finally { setLoading(false); } }, []); useEffect(() => { load(); }, [load]); return <PortalShell title="Coding problems" eyebrow="Practice makes progress"><div className="panel"><div className="panel-head"><p className="muted">Challenges from the server, with grading delegated to the configured safe runner.</p><Link href="/leaderboard">View leaderboard →</Link></div>{loading ? <LearnerLoading label="Loading coding problems…"/> : error ? <LearnerError message={error} retry={load}/> : items.length ? items.map((problem, index) => <div className="problem-row" key={problem.id}><div><span className={`difficulty d${index % 3}`}>Problem</span><h3>{problem.title}</h3><small className="muted">{problem.statement.slice(0, 120)}{problem.statement.length > 120 ? '…' : ''}</small></div><Link className="btn btn-soft" href={`/coding-problems/${problem.id}`}>Solve problem</Link></div>) : <LearnerEmpty>No coding problems are available yet.</LearnerEmpty>}</div></PortalShell>; }
