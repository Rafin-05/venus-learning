'use client';
import Link from 'next/link';
export default function ResendVerification(){return <main className="auth-wrap"><div className="auth"><div className="eyebrow">Account verification</div><h1>Email verification is disabled</h1><p className="muted">No verification email is needed. Your account works as soon as you create it — just sign in.</p><p><Link href="/login">Back to sign in</Link></p></div></main>;}
