'use client';
import Link from 'next/link';
import {ReactNode,useEffect,useState} from 'react';
import {useRouter} from 'next/navigation';
import {api} from '../lib/api';

type Props={title:string;eyebrow?:string;children:ReactNode;role?:string};
export default function PortalShell({title,eyebrow='Your learning space',children,role}:Props) {
 const router=useRouter();const [actual,setActual]=useState('');const [ready,setReady]=useState(false);const [error,setError]=useState('');const [loggingOut,setLoggingOut]=useState(false);
 useEffect(()=>{let active=true;api<{role:string}>('/auth/me/').then(user=>{if(active)setActual(user.role==='admin'?'Admin':user.role==='instructor'?'Instructor':'Learner');}).catch(err=>{if(active)setError(err.message || 'Please sign in to continue.');}).finally(()=>{if(active)setReady(true);});return()=>{active=false;};},[]);
 const learner=[['Overview','/dashboard'],['My learning','/my-learning'],['Certificates','/certificates'],['Coding problems','/coding-problems'],['Submissions','/submissions'],['Contests','/contests'],['Contest history','/contest-history'],['Leaderboard','/leaderboard'],['Report an issue','/report-issue'],['Profile settings','/profile']];
 const instructor=[['Overview','/instructor'],['My courses','/instructor/courses'],['Create course','/instructor/courses/new'],['Quiz manager','/instructor/quizzes'],['Report an issue','/report-issue'],['Profile settings','/profile']];
 const admin=[['Overview','/admin'],['Courses & approvals','/admin/courses'],['Users','/admin/users'],['Instructors','/admin/instructors'],['Quiz manager','/admin/quizzes'],['Coding problems','/admin/problems'],['Contests','/admin/contests'],['Issues','/admin/issues'],['Profile settings','/profile']];
 const items=actual==='Admin'?admin:actual==='Instructor'?instructor:learner;
 async function logout(){setLoggingOut(true);setError('');try{await api('/auth/logout/',{method:'POST'});router.push('/login');router.refresh();}catch(err){setError(err instanceof Error?err.message:'Unable to sign out.');setLoggingOut(false);}}
 if(!ready)return <main className="container section" aria-live="polite">Loading your workspace…</main>;
 if(!actual)return <main className="container section"><div className="panel"><h1>Sign in to continue</h1><p className="form-error">{error}</p><Link className="btn btn-primary" href="/login">Sign in</Link></div></main>;
 if(role&&role!==actual)return <main className="container section"><div className="panel"><h1>This workspace is not available for your account</h1><p>You are signed in as {actual.toLowerCase()}.</p><Link className="btn btn-primary" href={actual==='Admin'?'/admin':actual==='Instructor'?'/instructor':'/dashboard'}>Open my workspace</Link></div></main>;
 return <main className="portal container"><aside className="side"><div className="side-role">{actual} portal</div>{items.map(([label,href])=><Link key={href} href={href}>{label}</Link>)}<Link href="/" className="side-exit">← Back to Venus</Link><button className="btn btn-soft side-exit" type="button" disabled={loggingOut} onClick={logout}>{loggingOut?'Signing out…':'Sign out'}</button></aside><section className="portal-main"><div className="page-title"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1></div><div className="avatar">{actual.slice(0,2).toUpperCase()}</div></div>{error&&<div className="form-error" role="alert">{error}</div>}{children}</section></main>;
}
