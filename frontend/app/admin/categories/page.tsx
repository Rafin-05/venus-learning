'use client';
import { FormEvent, useState } from 'react';
import { AdminPage, useCollection, Notice, Action, post, remove } from '../_components';

// Admin-managed course categories. The instructor create flow fills its
// category dropdown from GET /categories/, so a category added here shows
// up there immediately. Deleting one never touches a course: courses store
// the category name as plain text, so they keep their old category.
export default function Categories() {
  const { data, loading, error, reload } = useCollection<any>('/categories/');
  const [name, setName] = useState('');
  const [formError, setFormError] = useState('');

  const add = async (e: FormEvent) => {
    e.preventDefault();
    if (!name.trim()) { setFormError('A category needs a name.'); return; }
    setFormError('');
    try {
      await post('/categories/', { name: name.trim() });
      setName('');
      reload();
    } catch (x) { setFormError(x instanceof Error ? x.message : 'Could not add this category.'); }
  };

  const del = async (id: number, label: string) => {
    if (!window.confirm(`Delete the “${label}” category? Courses already using it keep the name as plain text.`)) return;
    await remove(`/categories/${id}/`);
    reload();
  };

  return <AdminPage title="Course categories">
    <div className="panel">
      <h2>Categories</h2>
      <p className="muted">These are the options instructors pick from on the first page of course creation. Add one here and it appears in that dropdown straight away.</p>
      <Notice error={error} />
      {formError && <div className="form-error" role="alert">{formError}</div>}
      <form onSubmit={add} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end' }}>
        <div className="field" style={{ flex: '1 1 240px', margin: 0 }}>
          <label htmlFor="category-name">New category name</label>
          <input id="category-name" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Photography" maxLength={100} />
        </div>
        <button className="btn btn-primary" type="submit">Add category</button>
      </form>
      {loading ? <p>Loading categories…</p> : data.length === 0 ? <p className="muted">No categories yet.</p> : <div style={{ marginTop: 16 }}>
        {data.map((c: any) => <div className="problem-row" key={c.id}>
          <div><b>{c.name}</b></div>
          <span><Action label="Delete" onClick={() => void del(c.id, c.name)} /></span>
        </div>)}
      </div>}
    </div>
  </AdminPage>;
}
