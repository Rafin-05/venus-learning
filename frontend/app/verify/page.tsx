'use client';
import {Suspense,useEffect,useState} from 'react';
import {useParams,useSearchParams} from 'next/navigation';
import Link from 'next/link';
import {api} from '../../lib/api';
function Verification() {
  const route = useParams<{token?:string}>(); const query = useSearchParams();
  const token = route?.token || query.get('token');
  const [status,setStatus] = useState('Verifying your email…');
  useEffect(() => {if(!token){setStatus('No verification token was provided. Open the complete link in your email.');return;}let active = true;api(`/auth/verify/${encodeURIComponent(token)}/`).then(() => {if(active)setStatus('Your email is verified. You can now sign in.');}).catch(err => {if(active)setStatus(err.message || 'This link is invalid or has expired.');});return () => {active=false;};},[token]);
  return <main className="auth-wrap"><div className="auth"><div className="eyebrow">Venus Learning</div><h1>Email verification</h1><p role="status">{status}</p><p className="muted">Instructor accounts also require administrator approval.</p><Link className="btn btn-primary" href="/login">Continue to sign in</Link><p><Link href="/resend-verification">Need a new verification link?</Link></p></div></main>;
}
export default function Verify(){return <Suspense fallback={<main className="auth-wrap">Loading verification…</main>}><Verification/></Suspense>;}
