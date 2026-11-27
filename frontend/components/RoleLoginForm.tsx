'use client';
import {FormEvent, useState} from 'react';
import {useRouter} from 'next/navigation';
import Link from 'next/link';
import {api, post, User} from '../lib/api';

type Role = 'learner' | 'instructor';

const LABEL: Record<Role, string> = {learner: 'Learner', instructor: 'Instructor'};

export default function RoleLoginForm({role, eyebrow, title, subtitle, destination, otherHref, otherRole}: {
  role: Role;
  eyebrow: string;
  title: string;
  subtitle: string;
  destination: string;
  otherHref: string;
  otherRole: Role;
}) {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await post('/auth/login/', {email, password});
      const user = await api<User>('/auth/me/');
      if (user.role !== role) {
        // Wrong portal: sign the account straight back out so it does not
        // stay signed in here, then point at the right portal.
        try { await post('/auth/logout/', {}); } catch { /* Already signed out or unreachable; the error below still applies. */ }
        setError(`This portal is for ${LABEL[role]}s only. That account is a ${user.role}. Please use the ${LABEL[otherRole]} sign-in instead.`);
        return;
      }
      router.push(destination);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not sign in.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-wrap">
      <form className="auth" onSubmit={submit}>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p className="muted">{subtitle}</p>
        {error && <p className="form-error" role="alert">{error}</p>}
        <div className="field">
          <label htmlFor="role-login-email">Email</label>
          <input id="role-login-email" type="email" autoComplete="username" required value={email} onChange={event => setEmail(event.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="role-login-password">Password</label>
          <input id="role-login-password" type="password" autoComplete="current-password" required value={password} onChange={event => setPassword(event.target.value)} />
        </div>
        <p><Link href="/reset">Forgot password?</Link></p>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <p>Not a {LABEL[role].toLowerCase()}? <Link href={otherHref}>Sign in as {LABEL[otherRole].toLowerCase()}</Link></p>
        <p>New to Venus Learning? <Link href="/register">Create an account</Link></p>
      </form>
    </main>
  );
}
