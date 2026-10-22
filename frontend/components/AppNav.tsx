'use client';
import Link from 'next/link';
import {useEffect,useState} from 'react';
import {usePathname,useRouter} from 'next/navigation';
import {api,post,User} from '../lib/api';

export default function AppNav() {
  const pathname = usePathname(); const router = useRouter();
  const [user,setUser] = useState<User|null>(null); const [ready,setReady] = useState(false);
  const [error,setError] = useState('');
  useEffect(() => {let active = true;api<User>('/auth/me/').then(value => {if(active)setUser(value);}).catch(() => {if(active)setUser(null);}).finally(() => {if(active)setReady(true);});return () => {active=false;};},[pathname]);
  async function logout() {try {await post('/auth/logout/',{});setUser(null);router.push('/');router.refresh();} catch(err) {setError(err instanceof Error ? err.message : 'Could not sign out.');}}
  const workspace = user?.role === 'admin' ? '/admin' : user?.role === 'instructor' ? '/instructor' : '/dashboard';
  return <header className="nav"><div className="container navin"><Link href="/" className="brand"><img src="/venus-wordmark.png" alt="Venus Learning"/></Link><nav className="navlinks" aria-label="Main navigation"><Link href="/courses">Explore</Link><Link href={workspace}>My workspace</Link><Link href="/contests">Challenges</Link>{ready && user ? <><Link href="/profile">{user.full_name || 'Account'}</Link><button className="btn btn-soft keep" onClick={logout}>Sign out</button></> : <Link href="/login" className="btn btn-primary keep">Sign in</Link>}</nav></div>{error && <p role="alert" className="form-error container">{error}</p>}</header>;
}
