'use client';
import {Suspense,useEffect,useState} from 'react';
import Link from 'next/link';
import {useSearchParams} from 'next/navigation';
import PortalShell from '../../components/PortalShell';
import {api,list} from '../../lib/api';
import {LearnerError,LearnerEmpty,LearnerLoading} from '../../components/LearnerStates';

function Rankings() {
  const params = useSearchParams(); const contest = params.get('contest');
  const [rows,setRows] = useState<any[]>([]);const [loading,setLoading] = useState(true);const [error,setError] = useState('');
  useEffect(() => {setLoading(true);setError('');if(contest && !/^\d+$/.test(contest)){setError('Invalid contest.');setLoading(false);return;}api(contest ? `/contests/${contest}/leaderboard/` : '/leaderboard/').then(data => setRows(list(data))).catch(err => setError(err.message)).finally(() => setLoading(false));},[contest]);
  return <PortalShell title={contest ? 'Contest leaderboard' : 'Community leaderboard'} eyebrow="Learning, together"><p><Link href="/contests" className="text-link">Browse contests</Link> · <Link href="/contest-history" className="text-link">My contest history</Link>{contest && <> · <Link href="/leaderboard" className="text-link">Community rankings</Link></>}</p>{loading ? <LearnerLoading label="Loading rankings…"/> : error ? <LearnerError message={error}/> : !rows.length ? <LearnerEmpty>No scores have been recorded yet.</LearnerEmpty> : <div className="panel"><div className="leader-row head"><span>Rank</span><span>Learner</span><span>{contest ? 'Score' : 'Points'}</span></div>{rows.map((row,index) => {const name = row.full_name || row.learner_name || row.learner || row.name || 'Learner';return <div className="leader-row" key={row.id || `${name}-${index}`}><strong>#{String(index+1).padStart(2,'0')}</strong><span className="leader-name"><i>{String(name).slice(0,1).toUpperCase()}</i>{String(name)}</span><b>{Number(contest ? row.score : row.points) || 0}</b></div>;})}</div>}</PortalShell>;
}
export default function Leaderboard() {return <Suspense fallback={<main className="container section">Loading rankings…</main>}><Rankings/></Suspense>;}
