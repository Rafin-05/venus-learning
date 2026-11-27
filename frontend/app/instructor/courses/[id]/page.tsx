'use client';
import { FormEvent, useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import PortalShell from '../../../../components/PortalShell';
import { api, list, patch, post } from '../../../../lib/api';
import AssetUpload from '../../../../components/AssetUpload';

type Lesson = { id: number; title: string; description?: string; lesson_type: string; content: string; video_url: string; provider?: string; provider_video_id?: string; document_url: string; coding_language: string; coding_boilerplate: string; coding_expected_output: string; position: number; duration_seconds?: number | null; is_preview?: boolean; is_required?: boolean; unit: number };
type Unit = { id: number; title: string; position: number; lessons: Lesson[] };
type Course = { id: number; title: string; subtitle?: string; description: string; category: string; subcategory?: string; level: string; language?: string; thumbnail: string; promo_video_url?: string; outcomes?: string[]; target_audience?: string; prerequisites?: string; price?: number | string; is_free?: boolean; enrollment_open?: boolean; access_duration_days?: number | null; completion_threshold?: number; status: string; units: Unit[] };

const blankLesson = () => ({ title: '', description: '', lesson_type: 'document', content: '', video_url: '', document_url: '', coding_language: '', coding_boilerplate: '', coding_expected_output: '', duration_seconds: '' as any, is_preview: false, is_required: true });
const assetIdFromUrl = (url: string) => url.match(/\/uploads\/([0-9a-f-]{36})\/content\//)?.[1] || '';

export default function CourseEditor() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const courseId = Number(id);
  const [c, setC] = useState<Course | null>(null);
  const [f, setF] = useState({ title: '', subtitle: '', description: '', category: '', subcategory: '', level: '', language: 'en', thumbnail: '', promo_video_url: '', outcomesText: '', target_audience: '', prerequisites: '', is_free: true, price: '0.00', enrollment_open: true, access_duration_days: '', completion_threshold: 90 });
  const [l, setL] = useState<any>(blankLesson());
  const [unitTitle, setUnitTitle] = useState('');
  const [selected, setSelected] = useState<number | null>(null);
  const [editLesson, setEditLesson] = useState<number | null>(null);
  const [editUnit, setEditUnit] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [students, setStudents] = useState<any[]>([]);
  const [reviews, setReviews] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [resources, setResources] = useState<any[]>([]);
  const [assignments, setAssignments] = useState<any[]>([]);
  const [resourceForm, setResourceForm] = useState({ title: '', description: '', lesson: '', external_url: '', asset: '' });
  const [assignmentForm, setAssignmentForm] = useState({ title: '', instructions: '', due_at: '', max_points: 100, rubric: '', accepted_types: 'both', is_required: false, lesson: '' });
  const [subs, setSubs] = useState<Record<number, any[]>>({});
  const [gradeForm, setGradeForm] = useState<Record<number, { score: string; feedback: string; status: string }>>({});

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const x = await api<Course>(`/courses/${id}/`);
      setC(x);
      const [studentData, reviewData, historyData, resourceData, assignmentData] = await Promise.all([
        api(`/courses/${id}/students/`), api(`/courses/${id}/reviews/`), api(`/courses/${id}/review-history/`).catch(() => []),
        api(`/resources/?course=${id}`), api(`/assignments/?course=${id}`),
      ]);
      setStudents(list(studentData)); setReviews(list(reviewData)); setHistory(list(historyData));
      setResources(list(resourceData)); setAssignments(list(assignmentData));
      setF({
        title: x.title, subtitle: x.subtitle || '', description: x.description, category: x.category, subcategory: x.subcategory || '',
        level: x.level || '', language: x.language || 'en', thumbnail: x.thumbnail || '', promo_video_url: x.promo_video_url || '',
        outcomesText: (x.outcomes || []).join('\n'), target_audience: x.target_audience || '', prerequisites: x.prerequisites || '',
        is_free: x.is_free !== false, price: x.is_free === false ? String(x.price ?? '0.00') : '0.00',
        enrollment_open: x.enrollment_open !== false, access_duration_days: x.access_duration_days ? String(x.access_duration_days) : '',
        completion_threshold: x.completion_threshold ?? 90,
      });
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load course.'); } finally { setLoading(false); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);

  const fail = (e: unknown, fallback: string) => setError(e instanceof Error ? e.message : fallback);

  async function saveCourse(e: FormEvent) {
    e.preventDefault();
    if (!f.title.trim() || !f.description.trim()) { setError('Title and description are required.'); return; }
    setBusy(true); setError('');
    try {
      await patch(`/courses/${courseId}/`, {
        title: f.title.trim(), subtitle: f.subtitle.trim(), description: f.description.trim(),
        category: f.category.trim(), subcategory: f.subcategory.trim(), level: f.level, language: f.language || 'en',
        thumbnail: f.thumbnail, promo_video_url: f.promo_video_url.trim(),
        outcomes: f.outcomesText.split('\n').map(s => s.trim()).filter(Boolean),
        target_audience: f.target_audience.trim(), prerequisites: f.prerequisites.trim(),
        is_free: f.is_free, price: f.is_free ? '0.00' : f.price, enrollment_open: f.enrollment_open,
        access_duration_days: f.access_duration_days === '' ? null : Number(f.access_duration_days),
        completion_threshold: f.completion_threshold,
      });
      setNotice('Course details saved. Editing a published course sends it back for review.');
      await load();
    } catch (e) { fail(e, 'Unable to save course.'); } finally { setBusy(false); }
  }

  async function submitReview() {
    setBusy(true); setError(''); setNotice('');
    try {
      await post(`/courses/${courseId}/submit-review/`, {});
      router.push(`/instructor/courses/${courseId}/review-submitted`);
    } catch (e) { fail(e, 'Unable to submit for review.'); } finally { setBusy(false); }
  }

  async function saveUnit(e: FormEvent) {
    e.preventDefault();
    if (!unitTitle.trim()) { setError('Unit title is required.'); return; }
    setBusy(true);
    try {
      if (editUnit) await patch(`/units/${editUnit}/`, { title: unitTitle });
      else await post('/units/', { course: courseId, title: unitTitle, position: c?.units.length || 0 });
      setUnitTitle(''); setEditUnit(null); await load();
    } catch (e) { fail(e, 'Unable to save unit.'); } finally { setBusy(false); }
  }

  async function remove(path: string) {
    if (!window.confirm('Delete this item? This cannot be undone.')) return;
    setBusy(true);
    try { await api(path, { method: 'DELETE' }); await load(); } catch (e) { fail(e, 'Unable to delete item.'); } finally { setBusy(false); }
  }

  async function move(u: Unit, d: number) {
    const n = c?.units.find(x => x.position === u.position + d);
    if (!n) return;
    setBusy(true);
    try { await patch(`/units/${u.id}/`, { position: n.position }); await patch(`/units/${n.id}/`, { position: u.position }); await load(); } catch (e) { fail(e, 'Unable to reorder units.'); } finally { setBusy(false); }
  }

  async function saveLesson(e: FormEvent) {
    e.preventDefault();
    if (selected === null || !l.title.trim()) { setError('Select a unit and provide a lesson title.'); return; }
    setBusy(true);
    try {
      const body = { ...l, unit: selected, duration_seconds: l.duration_seconds === '' ? null : Number(l.duration_seconds), ...(editLesson ? {} : { position: c?.units.find(u => u.id === selected)?.lessons.length || 0 }) };
      if (editLesson) await patch(`/lessons/${editLesson}/`, body);
      else await post('/lessons/', body);
      setL(blankLesson()); setEditLesson(null); await load();
    } catch (e) { fail(e, 'Unable to save lesson.'); } finally { setBusy(false); }
  }

  async function saveResource(e: FormEvent) {
    e.preventDefault();
    if (!resourceForm.title.trim()) { setError('Resource title is required.'); return; }
    setBusy(true);
    try {
      await post('/resources/', { course: courseId, lesson: resourceForm.lesson ? Number(resourceForm.lesson) : null, title: resourceForm.title.trim(), description: resourceForm.description.trim(), external_url: resourceForm.external_url.trim(), asset: resourceForm.asset || null });
      setResourceForm({ title: '', description: '', lesson: '', external_url: '', asset: '' }); await load();
    } catch (e) { fail(e, 'Unable to save resource.'); } finally { setBusy(false); }
  }

  async function saveAssignment(e: FormEvent) {
    e.preventDefault();
    if (!assignmentForm.title.trim() || !assignmentForm.instructions.trim()) { setError('Assignment title and instructions are required.'); return; }
    setBusy(true);
    try {
      await post('/assignments/', { course: courseId, lesson: assignmentForm.lesson ? Number(assignmentForm.lesson) : null, title: assignmentForm.title.trim(), instructions: assignmentForm.instructions.trim(), due_at: assignmentForm.due_at || null, max_points: assignmentForm.max_points, rubric: assignmentForm.rubric.trim(), accepted_types: assignmentForm.accepted_types, is_required: assignmentForm.is_required });
      setAssignmentForm({ title: '', instructions: '', due_at: '', max_points: 100, rubric: '', accepted_types: 'both', is_required: false, lesson: '' }); await load();
    } catch (e) { fail(e, 'Unable to save assignment.'); } finally { setBusy(false); }
  }

  async function loadSubs(assignmentId: number) {
    try { const rows = list(await api(`/assignment-submissions/?assignment=${assignmentId}`)); setSubs(old => ({ ...old, [assignmentId]: rows })); } catch (e) { fail(e, 'Unable to load submissions.'); }
  }

  async function grade(submissionId: number, assignmentId: number) {
    const g = gradeForm[submissionId];
    if (!g) return;
    setBusy(true);
    try {
      await post(`/assignment-submissions/${submissionId}/grade/`, { score: g.status === 'graded' ? Number(g.score) : null, feedback: g.feedback, status: g.status });
      await loadSubs(assignmentId);
    } catch (e) { fail(e, 'Unable to grade submission.'); } finally { setBusy(false); }
  }

  if (loading && !c) return <PortalShell title="Course editor" role="Instructor"><p className="muted">Loading curriculum…</p></PortalShell>;
  const allLessons = c?.units.flatMap(u => u.lessons) || [];
  return <PortalShell title={c?.title || 'Course editor'} role="Instructor">
    <div className="panel">
      <h2>Course details</h2>
      <p className="muted">Status: <b>{c?.status}</b>{c?.status === 'pending' ? ' — a draft or awaiting admin review. Learners cannot see it yet.' : ''}</p>
      {error && <div className="form-error" role="alert">{error}</div>}
      {notice && <p className="success">{notice}</p>}
      <AssetUpload purpose="thumbnail" course={courseId} onUploaded={url => setF(x => ({ ...x, thumbnail: url }))} />
      <AssetUpload purpose="document" course={courseId} onUploaded={url => setL((x: any) => ({ ...x, document_url: url }))} />
      <form onSubmit={saveCourse}>
        <div className="field"><label htmlFor="title">Title *</label><input id="title" required value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /></div>
        <div className="field"><label htmlFor="subtitle">Subtitle</label><input id="subtitle" value={f.subtitle} onChange={e => setF({ ...f, subtitle: e.target.value })} /></div>
        <div className="field"><label htmlFor="description">Description *</label><textarea id="description" rows={5} required value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></div>
        <div className="field"><label htmlFor="category">Category</label><input id="category" value={f.category} onChange={e => setF({ ...f, category: e.target.value })} /></div>
        <div className="field"><label htmlFor="subcategory">Subcategory</label><input id="subcategory" value={f.subcategory} onChange={e => setF({ ...f, subcategory: e.target.value })} /></div>
        <div className="field"><label htmlFor="level">Level</label><select id="level" value={f.level} onChange={e => setF({ ...f, level: e.target.value })}><option value="">Choose a level</option><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></div>
        <div className="field"><label htmlFor="language">Language</label><input id="language" value={f.language} onChange={e => setF({ ...f, language: e.target.value })} /></div>
        <div className="field"><label htmlFor="thumbnail">Thumbnail URL</label><input id="thumbnail" type="url" value={f.thumbnail} onChange={e => setF({ ...f, thumbnail: e.target.value })} /></div>
        <div className="field"><label htmlFor="promo">Promotional video (YouTube link)</label><input id="promo" type="url" value={f.promo_video_url} onChange={e => setF({ ...f, promo_video_url: e.target.value })} /></div>
        <div className="field"><label htmlFor="outcomes">What learners will learn (one per line)</label><textarea id="outcomes" rows={4} value={f.outcomesText} onChange={e => setF({ ...f, outcomesText: e.target.value })} /></div>
        <div className="field"><label htmlFor="audience">Target audience</label><textarea id="audience" rows={2} value={f.target_audience} onChange={e => setF({ ...f, target_audience: e.target.value })} /></div>
        <div className="field"><label htmlFor="prereq">Prerequisites</label><textarea id="prereq" rows={2} value={f.prerequisites} onChange={e => setF({ ...f, prerequisites: e.target.value })} /></div>
        <div className="field"><label><input type="checkbox" checked={f.is_free} onChange={e => setF({ ...f, is_free: e.target.checked })} /> Free course</label></div>
        {!f.is_free && <div className="field"><label htmlFor="price">Price</label><input id="price" type="number" min="0" step="0.01" value={f.price} onChange={e => setF({ ...f, price: e.target.value })} /></div>}
        <div className="field"><label><input type="checkbox" checked={f.enrollment_open} onChange={e => setF({ ...f, enrollment_open: e.target.checked })} /> Enrollment open</label></div>
        <div className="field"><label htmlFor="access">Access duration (days, blank = no expiry)</label><input id="access" type="number" min="1" value={f.access_duration_days} onChange={e => setF({ ...f, access_duration_days: e.target.value })} /></div>
        <div className="field"><label htmlFor="threshold">Video completion threshold (%)</label><input id="threshold" type="number" min="1" max="100" value={f.completion_threshold} onChange={e => setF({ ...f, completion_threshold: Number(e.target.value) })} /></div>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Saving…' : 'Save course details'}</button>{' '}
        <button type="button" className="btn btn-soft" disabled={busy} onClick={submitReview}>Submit for admin review</button>
      </form>
      {history.length > 0 && <div style={{ marginTop: 16 }}><h3>Review history</h3>{history.map((h: any) => <p key={h.id} className="muted">{h.decision.replaceAll('_', ' ')} · {h.reviewer_name || 'Instructor'}{h.notes ? ` — ${h.notes}` : ''} · {h.created_at ? new Date(h.created_at).toLocaleString() : ''}</p>)}</div>}
    </div>

    <div className="panel">
      <div className="panel-head"><div><h2>Curriculum</h2><p className="muted">Sections and learning items in order. Video, resource, quiz and assignment items are all lessons in a section.</p></div>
        <form onSubmit={saveUnit}><label htmlFor="unit-title">{editUnit ? 'Rename unit' : 'New unit'}</label><input id="unit-title" value={unitTitle} onChange={e => setUnitTitle(e.target.value)} placeholder="Unit title" /><button className="btn btn-primary" disabled={busy}>{editUnit ? 'Save unit' : 'Add unit'}</button></form>
      </div>
      {c?.units.map(u => <div className="panel" key={u.id}>
        <div className="panel-head"><div><h3>{u.position + 1}. {u.title}</h3><small className="muted">{u.lessons.length} lessons</small></div>
          <span><button className="btn btn-soft" onClick={() => { setEditUnit(u.id); setUnitTitle(u.title); }}>Rename</button><button className="btn btn-soft" disabled={!u.position || busy} onClick={() => void move(u, -1)}>↑</button><button className="btn btn-soft" disabled={u.position === c.units.length - 1 || busy} onClick={() => void move(u, 1)}>↓</button><button className="btn btn-soft" onClick={() => void remove(`/units/${u.id}/`)}>Delete</button></span>
        </div>
        {u.lessons.map(x => <div className="problem-row" key={x.id}><div><b>{x.position + 1}. {x.title}</b><small className="muted">{x.lesson_type}{x.is_preview ? ' · free preview' : ''}{x.is_required === false ? ' · optional' : ''}{x.provider_video_id ? ` · YouTube ${x.provider_video_id}` : ''}</small></div><span><button className="btn btn-soft" onClick={() => { setSelected(u.id); setEditLesson(x.id); setL({ ...blankLesson(), ...x, duration_seconds: x.duration_seconds ?? '' }); }}>Edit</button><button className="btn btn-soft" onClick={() => void remove(`/lessons/${x.id}/`)}>Delete</button></span></div>)}
        <button className="btn btn-soft" onClick={() => { setSelected(u.id); setEditLesson(null); setL(blankLesson()); }}>+ Add lesson</button>
      </div>)}
    </div>

    <div className="panel"><h2>{editLesson ? 'Edit lesson' : 'New lesson'}</h2>
      <form onSubmit={saveLesson}>
        <div className="field"><label htmlFor="lesson-unit">Unit</label><select id="lesson-unit" value={selected ?? ''} onChange={e => setSelected(Number(e.target.value) || null)}><option value="">Choose a unit</option>{c?.units.map(u => <option key={u.id} value={u.id}>{u.title}</option>)}</select></div>
        <div className="field"><label htmlFor="lesson-title">Title *</label><input id="lesson-title" required value={l.title} onChange={e => setL({ ...l, title: e.target.value })} /></div>
        <div className="field"><label htmlFor="lesson-description">Description</label><textarea id="lesson-description" rows={2} value={l.description} onChange={e => setL({ ...l, description: e.target.value })} /></div>
        <div className="field"><label htmlFor="lesson-type">Lesson type</label><select id="lesson-type" value={l.lesson_type} onChange={e => setL({ ...l, lesson_type: e.target.value })}><option value="video">Video</option><option value="document">Document</option><option value="coding">Coding</option><option value="resource">Resource</option><option value="quiz">Quiz</option><option value="assignment">Assignment</option></select></div>
        <div className="field"><label htmlFor="lesson-video">Video URL (YouTube)</label><input id="lesson-video" type="url" value={l.video_url} onChange={e => setL({ ...l, video_url: e.target.value })} /><small className="muted">The YouTube video ID is extracted and validated on the server. Unlisted videos can be embedded for enrolled learners but are not private.</small></div>
        <div className="field"><label htmlFor="lesson-document">Document URL</label><input id="lesson-document" type="url" value={l.document_url} onChange={e => setL({ ...l, document_url: e.target.value })} /></div>
        <div className="field"><label htmlFor="lesson-content">Content / instructions</label><textarea id="lesson-content" rows={3} value={l.content} onChange={e => setL({ ...l, content: e.target.value })} /></div>
        <div className="field"><label htmlFor="lesson-duration">Duration (seconds)</label><input id="lesson-duration" type="number" min="0" value={l.duration_seconds} onChange={e => setL({ ...l, duration_seconds: e.target.value })} /></div>
        <div className="field"><label><input type="checkbox" checked={l.is_preview} onChange={e => setL({ ...l, is_preview: e.target.checked })} /> Free preview — anyone can watch this lesson on the approved course page</label></div>
        <div className="field"><label><input type="checkbox" checked={l.is_required} onChange={e => setL({ ...l, is_required: e.target.checked })} /> Required for course completion</label></div>
        {l.lesson_type === 'coding' && <>
          <div className="field"><label htmlFor="lesson-lang">Coding language</label><input id="lesson-lang" value={l.coding_language} onChange={e => setL({ ...l, coding_language: e.target.value })} /></div>
          <div className="field"><label htmlFor="lesson-boiler">Coding boilerplate</label><textarea id="lesson-boiler" rows={3} value={l.coding_boilerplate} onChange={e => setL({ ...l, coding_boilerplate: e.target.value })} /></div>
          <div className="field"><label htmlFor="lesson-output">Coding expected output</label><textarea id="lesson-output" rows={3} value={l.coding_expected_output} onChange={e => setL({ ...l, coding_expected_output: e.target.value })} /></div>
        </>}
        <button className="btn btn-primary" disabled={busy || selected === null}>{busy ? 'Saving…' : editLesson ? 'Save lesson' : 'Add lesson'}</button>{editLesson && <button type="button" className="btn btn-soft" onClick={() => { setEditLesson(null); setL(blankLesson()); }}>Cancel</button>}
      </form>
    </div>

    <div className="panel"><h2>Learning resources</h2><p className="muted">PDF and other files for the course, or attached to one lesson. Only enrolled learners can download them.</p>
      {resources.length === 0 ? <p className="muted">No resources yet.</p> : resources.map((r: any) => <div className="problem-row" key={r.id}><div><b>{r.title}</b><small className="muted">{r.lesson ? `Lesson ${r.lesson}` : 'Course level'} · {r.original_name || r.external_url || ''}</small></div><span><a className="btn btn-soft" href={r.download_url} target="_blank" rel="noopener noreferrer">Open</a> <button className="btn btn-soft" onClick={() => void remove(`/resources/${r.id}/`)}>Delete</button></span></div>)}
      <form onSubmit={saveResource} style={{ marginTop: 16 }}>
        <div className="field"><label htmlFor="res-title">Resource title</label><input id="res-title" required value={resourceForm.title} onChange={e => setResourceForm({ ...resourceForm, title: e.target.value })} /></div>
        <div className="field"><label htmlFor="res-desc">Description</label><textarea id="res-desc" rows={2} value={resourceForm.description} onChange={e => setResourceForm({ ...resourceForm, description: e.target.value })} /></div>
        <div className="field"><label htmlFor="res-lesson">Attach to lesson (optional)</label><select id="res-lesson" value={resourceForm.lesson} onChange={e => setResourceForm({ ...resourceForm, lesson: e.target.value })}><option value="">Course level</option>{allLessons.map(x => <option key={x.id} value={x.id}>{x.title}</option>)}</select></div>
        <AssetUpload purpose="document" course={courseId} onUploaded={url => setResourceForm(x => ({ ...x, asset: assetIdFromUrl(url), external_url: '' }))} />
        {resourceForm.asset && <p className="muted">Uploaded file attached. Clear it to use a link instead: <button type="button" className="btn btn-soft" onClick={() => setResourceForm(x => ({ ...x, asset: '' }))}>Use a link</button></p>}
        {!resourceForm.asset && <div className="field"><label htmlFor="res-url">Or external link</label><input id="res-url" type="url" value={resourceForm.external_url} onChange={e => setResourceForm({ ...resourceForm, external_url: e.target.value })} /></div>}
        <button className="btn btn-primary" disabled={busy}>Add resource</button>
      </form>
    </div>

    <div className="panel"><h2>Assignments</h2><p className="muted">Homework with due dates and file or text submissions. Quizzes are managed on the <a href="/instructor/quizzes">quiz page</a> and can be linked to a lesson there.</p>
      {assignments.length === 0 ? <p className="muted">No assignments yet.</p> : assignments.map((a: any) => <div className="panel" key={a.id}>
        <div className="panel-head"><div><h3>{a.title}</h3><small className="muted">{a.max_points} points · {a.accepted_types}{a.is_required ? ' · required' : ''}{a.due_at ? ` · due ${new Date(a.due_at).toLocaleString()}` : ''}</small></div>
          <span><button className="btn btn-soft" onClick={() => void loadSubs(a.id)}>Submissions</button><button className="btn btn-soft" onClick={() => void remove(`/assignments/${a.id}/`)}>Delete</button></span>
        </div>
        <p>{a.instructions}</p>
        {(subs[a.id] || []).length === 0 ? <p className="muted">No submissions loaded.</p> : subs[a.id].map((s: any) => <div className="problem-row" key={s.id}><div><b>{s.learner_name || 'Learner'}</b><small className="muted">Attempt {s.attempt_no} · {s.status}{s.score !== null && s.score !== undefined ? ` · ${s.score} points` : ''}</small><p>{s.text_response}</p></div>
          <span>
            <input type="number" min="0" max={a.max_points} placeholder="Score" style={{ width: 80 }} value={gradeForm[s.id]?.score || ''} onChange={e => setGradeForm(old => ({ ...old, [s.id]: { ...(old[s.id] || { score: '', feedback: '', status: 'graded' }), score: e.target.value } }))} />
            <input type="text" placeholder="Feedback" value={gradeForm[s.id]?.feedback || ''} onChange={e => setGradeForm(old => ({ ...old, [s.id]: { ...(old[s.id] || { score: '', feedback: '', status: 'graded' }), feedback: e.target.value } }))} />
            <select value={gradeForm[s.id]?.status || 'graded'} onChange={e => setGradeForm(old => ({ ...old, [s.id]: { ...(old[s.id] || { score: '', feedback: '', status: 'graded' }), status: e.target.value } }))}><option value="graded">Graded</option><option value="needs_resubmission">Needs resubmission</option></select>
            <button className="btn btn-soft" onClick={() => void grade(s.id, a.id)}>Grade</button>
          </span></div>)}
      </div>)}
      <form onSubmit={saveAssignment} style={{ marginTop: 16 }}>
        <div className="field"><label htmlFor="asg-title">Title</label><input id="asg-title" required value={assignmentForm.title} onChange={e => setAssignmentForm({ ...assignmentForm, title: e.target.value })} /></div>
        <div className="field"><label htmlFor="asg-inst">Instructions</label><textarea id="asg-inst" rows={3} required value={assignmentForm.instructions} onChange={e => setAssignmentForm({ ...assignmentForm, instructions: e.target.value })} /></div>
        <div className="field"><label htmlFor="asg-due">Due date (optional)</label><input id="asg-due" type="datetime-local" value={assignmentForm.due_at} onChange={e => setAssignmentForm({ ...assignmentForm, due_at: e.target.value })} /></div>
        <div className="field"><label htmlFor="asg-points">Points</label><input id="asg-points" type="number" min="1" value={assignmentForm.max_points} onChange={e => setAssignmentForm({ ...assignmentForm, max_points: Number(e.target.value) })} /></div>
        <div className="field"><label htmlFor="asg-rubric">Rubric</label><textarea id="asg-rubric" rows={2} value={assignmentForm.rubric} onChange={e => setAssignmentForm({ ...assignmentForm, rubric: e.target.value })} /></div>
        <div className="field"><label htmlFor="asg-type">Accepted submission</label><select id="asg-type" value={assignmentForm.accepted_types} onChange={e => setAssignmentForm({ ...assignmentForm, accepted_types: e.target.value })}><option value="both">File or text</option><option value="file">File upload</option><option value="text">Text response</option></select></div>
        <div className="field"><label htmlFor="asg-lesson">Link to lesson (optional)</label><select id="asg-lesson" value={assignmentForm.lesson} onChange={e => setAssignmentForm({ ...assignmentForm, lesson: e.target.value })}><option value="">No lesson link</option>{allLessons.map(x => <option key={x.id} value={x.id}>{x.title}</option>)}</select></div>
        <div className="field"><label><input type="checkbox" checked={assignmentForm.is_required} onChange={e => setAssignmentForm({ ...assignmentForm, is_required: e.target.checked })} /> Required for course completion</label></div>
        <button className="btn btn-primary" disabled={busy}>Add assignment</button>
      </form>
    </div>

    <div className="panel"><h2>Students</h2>{students.length === 0 ? <p className="muted">No enrolled students yet.</p> : students.map((student: any, i) => <div className="problem-row" key={student.id || i}><span>{student.full_name || student.email || student.learner_name || 'Student'}</span><small className="muted">{student.progress_percent === undefined ? 'Enrolled' : `${student.progress_percent}% complete`}</small></div>)}</div>
    <div className="panel"><h2>Ratings and reviews</h2>{reviews.length === 0 ? <p className="muted">No reviews yet.</p> : reviews.map((review: any, i) => <div className="problem-row" key={review.id || i}><div><b>{review.rating}/5</b><p>{review.review || 'No written review.'}</p></div><small className="muted">{review.created_at ? new Date(review.created_at).toLocaleDateString() : ''}</small></div>)}</div>
  </PortalShell>;
}
