'use client';
import { useEffect, useState, ReactNode } from 'react';
import PortalShell from '../../components/PortalShell';
import { api, list, patch, post } from '../../lib/api';

export const remove = (path: string) => api(path, { method: 'DELETE' });

export function AdminPage({ title, children, eyebrow }: { title: string; children: ReactNode; eyebrow?: string }) {
  return <PortalShell title={title} role="Admin" eyebrow={eyebrow || 'Operations'}>{children}</PortalShell>;
}
export function Notice({ error }: { error?: string }) { return error ? <div className="form-error" role="alert">{error}</div> : null; }
export function useCollection<T = any>(path: string) {
  const [data, setData] = useState<T[]>([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const reload = () => { setLoading(true); setError(''); api(path).then(x => setData(list(x) as T[])).catch(e => setError(e instanceof Error ? e.message : 'Could not load this list.')).finally(() => setLoading(false)); };
  useEffect(reload, [path]); return { data, loading, error, reload };
}
export function Action({ label, onClick, tone = 'soft' }: { label: string; onClick: () => Promise<void> | void; tone?: string }) {
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  return <span><button className={'btn btn-' + tone} disabled={busy} onClick={async () => { setBusy(true); setError(''); try { await onClick(); } catch (e) { setError(e instanceof Error ? e.message : 'Action failed.'); } finally { setBusy(false); } }}>{busy ? 'Working…' : label}</button>{error && <small className="form-error" role="alert">{error}</small>}</span>;
}
export function Users() {
  const { data, loading, error, reload } = useCollection<any>('/staff/users/');
  const change = async (id: number, body: any) => { await patch(`/staff/users/${id}/`, body); reload(); };
  return <AdminPage title="Users & instructors"><div className="panel"><div className="panel-head"><div><h2>Account review</h2><p className="muted">Approve instructors and control active access.</p></div></div><Notice error={error}/>{loading ? <p>Loading accounts…</p> : <div className="table-wrap"><table className="table"><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Active</th><th>Instructor approved</th><th>Actions</th></tr></thead><tbody>{data.map(u => <tr key={u.id}><td>{u.full_name}</td><td>{u.email}</td><td>{u.role}</td><td>{String(u.is_active)}</td><td>{u.role === 'instructor' ? String(u.instructor_approved) : '—'}</td><td><Action label={u.is_active ? 'Block' : 'Unblock'} onClick={() => change(u.id, { is_active: !u.is_active })} />{' '}{u.role === 'instructor' && <Action label={u.instructor_approved ? 'Revoke approval' : 'Approve'} tone={u.instructor_approved ? 'soft' : 'primary'} onClick={() => change(u.id, { instructor_approved: !u.instructor_approved })} />}</td></tr>)}</tbody></table></div>}</div></AdminPage>;
}
export { api, list, patch, post };
