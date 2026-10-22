'use client';

import {FormEvent,useEffect,useState} from 'react';
import Link from 'next/link';
import {post} from '../../lib/api';

export default function ResendVerification() {
  const [email,setEmail] = useState('');
  const [busy,setBusy] = useState(false);
  const [message,setMessage] = useState('');
  const [error,setError] = useState('');
  const [cooldown,setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = window.setTimeout(() => setCooldown(value => Math.max(0,value - 1)),1000);
    return () => window.clearTimeout(timer);
  },[cooldown]);

  async function submit(event:FormEvent) {
    event.preventDefault();
    if (busy || cooldown > 0) return;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await post<{detail:string}>('/auth/resend-verification/',{email:email.trim()});
      setMessage(result.detail);
      setCooldown(60);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not request a verification email. Please try again later.');
    } finally {
      setBusy(false);
    }
  }

  return <main className="auth-wrap"><form className="auth" onSubmit={submit}>
    <div className="eyebrow">Account verification</div>
    <h1>Resend verification email</h1>
    <p className="muted">Already signed up but never received your email, or your link expired? Enter the same email address. You do not need to register again.</p>
    {error && <p className="form-error" role="alert">{error}</p>}
    {message && <p className="success" role="status">{message}</p>}
    <div className="field"><label htmlFor="resend-email">Email address</label><input id="resend-email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={event => setEmail(event.target.value)} /></div>
    <button className="btn btn-primary" disabled={busy || cooldown > 0}>{busy ? 'Requesting…' : cooldown > 0 ? `Try again in ${cooldown}s` : 'Send verification link'}</button>
    <p className="muted">Check your inbox and spam folder. If a new email is issued, only its latest verification link will work. Delivery depends on the site’s email service.</p>
    <p><Link href="/login">Back to sign in</Link></p>
  </form></main>;
}
