'use client';
import { FormEvent, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import PortalShell from '../../../../components/PortalShell';
import AssetUpload from '../../../../components/AssetUpload';
import { api, list, post } from '../../../../lib/api';

// Multi-page course creation.
//
// Step 1 — Course basics: thumbnail upload first, then title, description,
//   category (dropdown of every category in the platform, loaded from
//   GET /categories/ — an admin adds more at /admin/categories), level,
//   access duration, and paid-or-free (price only when Paid). "Next"
//   creates the course with the same POST /courses/ payload as before.
//   Nothing is sent to an admin here.
// Step 2 — Curriculum: the instructor creates units first. Lessons only
//   appear after a unit exists — nothing about lessons sits on the page
//   before that. Inside each unit there is one dropdown to add a lesson,
//   an assignment, a quiz, or the final exam. Lessons attach to the unit;
//   quizzes, assignments and the final exam are course-level items in the
//   API (Quiz/Assignment have no unit field), so they are created from
//   inside the unit panel but listed course-wide below.
// Final step — Submit for admin review: only after Step 2, POST
//   /courses/{id}/submit-review/ and land on the review-submitted
//   confirmation page. That call is the moment the course goes to an
//   admin as Pending — not before. (The status field itself reads
//   "pending" from creation, as it always has; see the note on the
//   submit panel. The review record, and the admin queue entry it
//   represents, are only created by this final call, which also requires
//   at least one unit and one lesson.)
type Question = { question: string; option_a: string; option_b: string; option_c: string; option_d: string; correct_answer: string };
type Category = { id: number; name: string };
type QuizItem = { id: number; title: string; is_final: boolean; pass_percentage: number; questions: Question[] };
type AssignmentItem = { id: number; title: string; max_points: number; due_at?: string | null };
type CurrLesson = { id: number; title: string; lesson_type: string; position: number; duration_seconds?: number | null; is_preview?: boolean; is_required?: boolean; provider_video_id?: string };
type CurrUnit = { id: number; title: string; position: number; lessons: CurrLesson[] };
type CreatedCourse = { id: number; title: string; status?: string };

const blankQ = (): Question => ({ question: '', option_a: '', option_b: '', option_c: '', option_d: '', correct_answer: 'a' });
const blankLesson = () => ({ title: '', description: '', lesson_type: 'video', content: '', video_url: '', document_url: '', coding_language: 'python', coding_boilerplate: '', coding_expected_output: '', duration_seconds: '' as any, is_preview: false, is_required: true });
const CODING_LANGUAGES = ['python', 'javascript', 'java', 'cpp', 'c', 'go', 'rust'];

export default function NewCourse() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2>(1);
  const [f, setF] = useState({
    title: '', subtitle: '', description: '', category: '', subcategory: '',
    level: '', language: 'en', thumbnail: '', promo_video_url: '',
    outcomesText: '', target_audience: '', prerequisites: '',
    is_free: true, price: '0.00', enrollment_open: true,
    access_duration_days: '', completion_threshold: 90,
  });
  const [categories, setCategories] = useState<Category[]>([]);
  const [categoriesFailed, setCategoriesFailed] = useState(false);
  const [created, setCreated] = useState<CreatedCourse | null>(null);
  const [units, setUnits] = useState<CurrUnit[]>([]);
  const [quizzes, setQuizzes] = useState<QuizItem[]>([]);
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  // Per-unit add panel: which unit the open form belongs to, and what kind.
  const [targetUnit, setTargetUnit] = useState<number | null>(null);
  const [addKind, setAddKind] = useState<'lesson' | 'quiz' | 'assignment' | 'final' | ''>('');
  const [unitTitle, setUnitTitle] = useState('');
  const [lesson, setLesson] = useState<any>(blankLesson());
  const [quizTitle, setQuizTitle] = useState('');
  const [passPercentage, setPassPercentage] = useState(70);
  const [questions, setQuestions] = useState<Question[]>([blankQ()]);
  const [asg, setAsg] = useState({ title: '', instructions: '', due_at: '', max_points: 100, rubric: '', accepted_types: 'both', is_required: false });

  const existingFinal = quizzes.find(q => q.is_final);
  const outcomes = f.outcomesText.split('\n').map(s => s.trim()).filter(Boolean);
  const lessonCount = units.reduce((n, u) => n + u.lessons.length, 0);
  const canSubmit = units.length > 0 && lessonCount > 0;

  useEffect(() => {
    api('/categories/').then(d => setCategories(list(d) as Category[])).catch(() => setCategoriesFailed(true));
  }, []);

  const loadCurriculum = useCallback(async (courseId: number) => {
    try {
      const [curr, q, a] = await Promise.all([
        api<any>(`/courses/${courseId}/curriculum/`),
        api(`/quizzes/?course=${courseId}`),
        api(`/assignments/?course=${courseId}`),
      ]);
      setUnits((curr.units || []) as CurrUnit[]);
      setQuizzes(list(q)); setAssignments(list(a));
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load the curriculum.'); }
  }, []);

  useEffect(() => { if (created) void loadCurriculum(created.id); }, [created, loadCurriculum]);

  // ---- Step 1: create the course, then move to Step 2 ----
  const createCourse = async (e: FormEvent) => {
    e.preventDefault();
    if (!f.title.trim() || !f.description.trim()) { setError('Title and description are required.'); return; }
    if (categories.length > 0 && !f.category) { setError('Choose a category.'); return; }
    if (!f.is_free && Number(f.price) <= 0) { setError('A paid course needs a price above 0.'); return; }
    if (f.completion_threshold < 1 || f.completion_threshold > 100) { setError('Completion threshold must be between 1 and 100.'); return; }
    setBusy(true); setError(''); setNotice('');
    try {
      const body = {
        title: f.title.trim(), subtitle: f.subtitle.trim(), description: f.description.trim(),
        category: f.category.trim(), subcategory: f.subcategory.trim(), level: f.level || '',
        language: f.language || 'en', thumbnail: f.thumbnail, promo_video_url: f.promo_video_url.trim(),
        outcomes, target_audience: f.target_audience.trim(), prerequisites: f.prerequisites.trim(),
        is_free: f.is_free, price: f.is_free ? '0.00' : f.price,
        enrollment_open: f.enrollment_open,
        access_duration_days: f.access_duration_days === '' ? null : Number(f.access_duration_days),
        completion_threshold: f.completion_threshold,
      };
      const c: any = await post('/courses/', body);
      setCreated({ id: c.id, title: c.title, status: c.status });
      setStep(2);
      setNotice(`Course “${c.title}” created. Now add units — nothing has been sent to an admin yet.`);
    } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  // ---- Step 2: units ----
  const saveUnit = async (e: FormEvent) => {
    e.preventDefault();
    if (!created || !unitTitle.trim()) { setError('Unit title is required.'); return; }
    setBusy(true); setError(''); setNotice('');
    try {
      await post('/units/', { course: created.id, title: unitTitle.trim(), position: units.length });
      setUnitTitle('');
      setNotice('Unit added. Add its lessons and other content inside it, below.');
      await loadCurriculum(created.id);
    } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  const removeUnit = async (id: number, title: string) => {
    if (!created || !window.confirm(`Delete the unit “${title}” and all its lessons? This cannot be undone.`)) return;
    setBusy(true);
    try { await api(`/units/${id}/`, { method: 'DELETE' }); if (targetUnit === id) { setTargetUnit(null); setAddKind(''); } await loadCurriculum(created.id); }
    catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  // ---- Step 2: lesson inside a unit (only after the unit exists) ----
  const pickAddKind = (unitId: number, kind: 'lesson' | 'quiz' | 'assignment' | 'final' | '') => {
    setTargetUnit(kind ? unitId : null);
    setAddKind(kind);
    setError('');
    if (kind === 'lesson') setLesson(blankLesson());
  };

  const setLessonType = (lessonType: string) => {
    // Switching type clears the other types' fields, so a video URL never
    // leaks into a document lesson (or the other way round).
    setLesson({ ...blankLesson(), title: lesson.title, description: lesson.description, lesson_type: lessonType });
  };

  const saveLesson = async (e: FormEvent) => {
    e.preventDefault();
    if (!created || targetUnit === null) return;
    if (!lesson.title.trim()) { setError('Lesson title is required.'); return; }
    if (lesson.lesson_type === 'video' && !lesson.video_url.trim()) { setError('A video lesson needs a YouTube URL.'); return; }
    if (lesson.lesson_type === 'document' && !lesson.document_url.trim() && !lesson.content.trim()) { setError('A document lesson needs an uploaded file, a link, or text content.'); return; }
    if (lesson.lesson_type === 'coding' && !lesson.coding_language) { setError('A coding lesson needs a language.'); return; }
    const unit = units.find(u => u.id === targetUnit);
    setBusy(true); setError(''); setNotice('');
    try {
      const body: any = {
        unit: targetUnit, title: lesson.title.trim(), description: lesson.description.trim(),
        lesson_type: lesson.lesson_type, position: unit ? unit.lessons.length : 0,
        duration_seconds: lesson.duration_seconds === '' ? null : Number(lesson.duration_seconds),
        is_preview: lesson.is_preview, is_required: lesson.is_required,
        content: '', video_url: '', document_url: '',
        coding_language: '', coding_boilerplate: '', coding_expected_output: '',
      };
      if (lesson.lesson_type === 'video') body.video_url = lesson.video_url.trim();
      if (lesson.lesson_type === 'document') { body.document_url = lesson.document_url.trim(); body.content = lesson.content; }
      if (lesson.lesson_type === 'coding') { body.coding_language = lesson.coding_language; body.coding_boilerplate = lesson.coding_boilerplate; body.coding_expected_output = lesson.coding_expected_output; }
      await post('/lessons/', body);
      setLesson(blankLesson());
      setNotice('Lesson added to this unit. Add another, or pick a different type from the dropdown.');
      await loadCurriculum(created.id);
    } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  const removeLesson = async (id: number, title: string) => {
    if (!created || !window.confirm(`Delete the lesson “${title}”? This cannot be undone.`)) return;
    setBusy(true);
    try { await api(`/lessons/${id}/`, { method: 'DELETE' }); await loadCurriculum(created.id); }
    catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  // ---- Step 2: quiz / assignment / final exam, created from inside a unit ----
  const saveContent = async (e: FormEvent) => {
    e.preventDefault();
    if (!created || (addKind !== 'assignment' && addKind !== 'quiz' && addKind !== 'final')) return;
    setError(''); setNotice('');
    if (addKind === 'assignment') {
      if (!asg.title.trim() || !asg.instructions.trim()) { setError('Assignment title and instructions are required.'); return; }
      setBusy(true);
      try {
        await post('/assignments/', {
          course: created.id, title: asg.title.trim(), instructions: asg.instructions.trim(),
          due_at: asg.due_at || null, max_points: asg.max_points, rubric: asg.rubric.trim(),
          accepted_types: asg.accepted_types, is_required: asg.is_required,
        });
        setAsg({ title: '', instructions: '', due_at: '', max_points: 100, rubric: '', accepted_types: 'both', is_required: false });
        setNotice('Assignment added.');
        await loadCurriculum(created.id);
      } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
      return;
    }
    const isFinal = addKind === 'final';
    if (!quizTitle.trim()) { setError(isFinal ? 'Final exam title is required.' : 'Quiz title is required.'); return; }
    if (questions.some(q => !q.question.trim() || !q.option_a.trim() || !q.option_b.trim() || !q.option_c.trim() || !q.option_d.trim())) {
      setError('Every question needs its text and all four options.'); return;
    }
    if (passPercentage < 1 || passPercentage > 100) { setError('Pass mark must be between 1 and 100.'); return; }
    if (isFinal && existingFinal) { setError(`This course already has a final exam (“${existingFinal.title}”).`); return; }
    setBusy(true);
    try {
      await post('/quizzes/', {
        course: created.id, title: quizTitle.trim(), is_final: isFinal,
        pass_percentage: passPercentage, questions,
      });
      setQuizTitle(''); setPassPercentage(70); setQuestions([blankQ()]);
      setNotice(isFinal ? 'Final exam added. It sits after all lessons, is taken only with camera monitoring, and passing it unlocks the certificate.' : 'Quiz added.');
      await loadCurriculum(created.id);
    } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  const removeContent = async (kind: 'quiz' | 'assignment', id: number) => {
    if (!created || !window.confirm('Delete this item? This cannot be undone.')) return;
    setBusy(true);
    try { await api(kind === 'quiz' ? `/quizzes/${id}/` : `/assignments/${id}/`, { method: 'DELETE' }); await loadCurriculum(created.id); }
    catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  // ---- Final step: submit for admin review ----
  const submitReview = async () => {
    if (!created) return;
    if (!canSubmit) { setError('Add at least one unit and one lesson before submitting for review.'); return; }
    setBusy(true); setError('');
    try {
      await post(`/courses/${created.id}/submit-review/`, {});
      router.push(`/instructor/courses/${created.id}/review-submitted`);
    } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  return <PortalShell title="Create course" role="Instructor">
    <div className="panel">
      <h2>{created ? `Course: ${created.title}` : 'New course'}</h2>
      <ol className="steps" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', listStyle: 'none', padding: 0, margin: '12px 0' }}>
        <li><button type="button" className="btn btn-soft" disabled={!created} onClick={() => setStep(1)}>{created ? '✓ ' : ''}Step 1 — Course basics</button></li>
        <li><button type="button" className="btn btn-soft" disabled={!created} onClick={() => setStep(2)}>{step === 2 ? '● ' : ''}Step 2 — Curriculum</button></li>
        <li><span className="btn btn-soft" aria-current={step === 2 ? 'step' : undefined}>Step 3 — Submit for review</span></li>
      </ol>
      {error && <div className="form-error" role="alert">{error}</div>}
      {notice && <p className="success">{notice}</p>}

      {step === 1 && !created && <form onSubmit={createCourse}>
        <h3>Step 1 — Course basics</h3>
        <p className="muted">Start with the thumbnail, then the basics. The course is only created when you press Next — nothing is sent to an admin on this page.</p>
        <div className="field"><label>Thumbnail *</label><AssetUpload purpose="thumbnail" onUploaded={url => setF({ ...f, thumbnail: url })} />
          {f.thumbnail && <img src={f.thumbnail} alt="Course thumbnail preview" style={{ width: '100%', maxWidth: 320, borderRadius: 12, marginTop: 8 }} />}
          <small className="muted">Upload an image file, or paste an image link below as a fallback.</small>
          <input type="url" placeholder="https://… (optional link fallback)" value={f.thumbnail} onChange={e => setF({ ...f, thumbnail: e.target.value })} />
        </div>
        <div className="field"><label htmlFor="title">Course title *</label><input id="title" required value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /></div>
        <div className="field"><label htmlFor="description">Description *</label><textarea id="description" rows={5} required value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></div>
        <div className="field"><label htmlFor="category">Category *</label>
          {categories.length > 0 ? <select id="category" required value={f.category} onChange={e => setF({ ...f, category: e.target.value })}>
            <option value="">Choose a category</option>
            {categories.map(c => <option key={c.id} value={c.name}>{c.name}</option>)}
          </select> : <input id="category" value={f.category} onChange={e => setF({ ...f, category: e.target.value })} placeholder="Category" />}
          {categoriesFailed && <small className="muted">Could not load the category list — type the category instead, or ask an admin to add categories at /admin/categories.</small>}
          {!categoriesFailed && categories.length === 0 && <small className="muted">No categories yet — ask an admin to add some, or type one here.</small>}
        </div>
        <div className="field"><label htmlFor="level">Level</label><select id="level" value={f.level} onChange={e => setF({ ...f, level: e.target.value })}><option value="">Choose a level</option><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></div>
        <div className="field"><label htmlFor="access">Access duration (days, blank = no expiry)</label><input id="access" type="number" min="1" value={f.access_duration_days} onChange={e => setF({ ...f, access_duration_days: e.target.value })} /></div>
        <div className="field"><label htmlFor="paid">Will this course be paid or free?</label>
          <select id="paid" value={f.is_free ? 'free' : 'paid'} onChange={e => setF({ ...f, is_free: e.target.value === 'free' })}>
            <option value="free">Free</option><option value="paid">Paid</option>
          </select>
        </div>
        {!f.is_free && <div className="field"><label htmlFor="price">Price *</label><input id="price" type="number" min="0" step="0.01" required value={f.price} onChange={e => setF({ ...f, price: e.target.value })} /><small className="muted">Payment collection is not built yet — paid courses cannot be enrolled in until a payment method is added.</small></div>}

        <h3>Optional details</h3>
        <div className="field"><label htmlFor="subtitle">Subtitle</label><input id="subtitle" value={f.subtitle} onChange={e => setF({ ...f, subtitle: e.target.value })} /></div>
        <div className="field"><label htmlFor="subcategory">Subcategory</label><input id="subcategory" value={f.subcategory} onChange={e => setF({ ...f, subcategory: e.target.value })} /></div>
        <div className="field"><label htmlFor="outcomes">What learners will learn (one per line)</label><textarea id="outcomes" rows={4} value={f.outcomesText} onChange={e => setF({ ...f, outcomesText: e.target.value })} placeholder={'Write a Python program\nUse lists and loops'} /></div>
        <div className="field"><label htmlFor="audience">Target audience</label><textarea id="audience" rows={2} value={f.target_audience} onChange={e => setF({ ...f, target_audience: e.target.value })} /></div>
        <div className="field"><label htmlFor="prereq">Prerequisites</label><textarea id="prereq" rows={2} value={f.prerequisites} onChange={e => setF({ ...f, prerequisites: e.target.value })} /></div>
        <div className="field"><label htmlFor="promo">Promotional video (optional, YouTube link)</label><input id="promo" type="url" placeholder="https://www.youtube.com/watch?v=…" value={f.promo_video_url} onChange={e => setF({ ...f, promo_video_url: e.target.value })} /></div>
        <div className="field"><label htmlFor="language">Language</label><input id="language" value={f.language} onChange={e => setF({ ...f, language: e.target.value })} /></div>
        <div className="field"><label><input type="checkbox" checked={f.enrollment_open} onChange={e => setF({ ...f, enrollment_open: e.target.checked })} /> Enrollment open</label></div>
        <div className="field"><label htmlFor="threshold">Video completion threshold (%)</label><input id="threshold" type="number" min="1" max="100" required value={f.completion_threshold} onChange={e => setF({ ...f, completion_threshold: Number(e.target.value) })} /><small className="muted">A video lesson counts as complete once this much has been watched. Default 90%.</small></div>
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Next: add units & lessons →'}</button>
      </form>}

      {step === 1 && created && <div>
        <h3>Step 1 — Course basics</h3>
        <p><b>{created.title}</b> — {f.category || 'No category'} · {f.level || 'No level'} · {f.is_free ? 'Free' : `Paid (${f.price})`} · access {f.access_duration_days ? `${f.access_duration_days} days` : 'no expiry'}</p>
        <p className="muted">{f.description}</p>
        <p className="muted">Basics are edited on the course editor, not here — the create form is only shown before the course exists.</p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={() => setStep(2)}>Continue to Step 2 — Curriculum →</button>
          <a className="btn btn-soft" href={`/instructor/courses/${created.id}`}>Edit basics on the course editor</a>
        </div>
      </div>}

      {step === 2 && created && <>
        <h3>Step 2 — Curriculum</h3>
        <p className="muted">Create a unit first. Its lessons, quizzes, assignments and the final exam are added inside it — they never appear before the unit exists.</p>

        {units.length === 0 && <p className="muted">No units yet. Create your first unit below to get started.</p>}
        {units.map((u, ui) => <div className="panel" key={u.id}>
          <h3>Unit {ui + 1}: {u.title}</h3>
          {u.lessons.length === 0
            ? <p className="muted">No lessons in this unit yet — pick what to add below.</p>
            : u.lessons.map(x => <div className="problem-row" key={x.id}><div><b>{x.position + 1}. {x.title}</b><small className="muted">{x.lesson_type}{x.duration_seconds ? ` · ${x.duration_seconds}s` : ''}{x.is_preview ? ' · free preview' : ''}{x.is_required === false ? ' · optional' : ''}{x.provider_video_id ? ` · YouTube ${x.provider_video_id}` : ''}</small></div><span><button className="btn btn-soft" onClick={() => void removeLesson(x.id, x.title)}>Delete</button></span></div>)}
          <div className="field"><label htmlFor={`add-${u.id}`}>Add to this unit</label>
            <select id={`add-${u.id}`} value={targetUnit === u.id ? addKind : ''} onChange={e => pickAddKind(u.id, e.target.value as 'lesson' | 'quiz' | 'assignment' | 'final' | '')}>
              <option value="">Choose what to add…</option>
              <option value="lesson">Lesson</option>
              <option value="assignment">Assignment</option>
              <option value="quiz">Quiz</option>
              <option value="final" disabled={!!existingFinal}>Final exam{existingFinal ? ' — already set' : ''}</option>
            </select>
            {addKind === 'final' && targetUnit === u.id && <small className="muted">Only one final exam per course. It appears after all lessons, is taken only with camera monitoring, and passing it unlocks the certificate.{existingFinal ? ` This course already has one (“${existingFinal.title}”).` : ''}</small>}
          </div>

          {targetUnit === u.id && addKind === 'lesson' && <form onSubmit={saveLesson}>
            <div className="field"><label htmlFor="lesson-title">Lesson title *</label><input id="lesson-title" required value={lesson.title} onChange={e => setLesson({ ...lesson, title: e.target.value })} /></div>
            <div className="field"><label htmlFor="lesson-type">Lesson type</label><select id="lesson-type" value={lesson.lesson_type} onChange={e => setLessonType(e.target.value)}><option value="video">Video</option><option value="document">Document</option><option value="coding">Coding</option></select></div>
            <div className="field"><label htmlFor="lesson-desc">Description</label><textarea id="lesson-desc" rows={2} value={lesson.description} onChange={e => setLesson({ ...lesson, description: e.target.value })} /></div>
            {lesson.lesson_type === 'video' && <>
              <div className="field"><label htmlFor="lesson-video">Video URL (YouTube) *</label><input id="lesson-video" type="url" required value={lesson.video_url} onChange={e => setLesson({ ...lesson, video_url: e.target.value })} /><small className="muted">The YouTube video ID is extracted and validated on the server.</small></div>
              <div className="field"><label htmlFor="lesson-duration">Duration (seconds)</label><input id="lesson-duration" type="number" min="0" value={lesson.duration_seconds} onChange={e => setLesson({ ...lesson, duration_seconds: e.target.value })} /></div>
            </>}
            {lesson.lesson_type === 'document' && <>
              <div className="field"><label>Document file</label><AssetUpload purpose="document" course={created.id} onUploaded={url => setLesson((x: any) => ({ ...x, document_url: url }))} />
                {lesson.document_url && <small className="muted">Uploaded: {lesson.document_url}</small>}
                <small className="muted">Or paste a document link below as a fallback.</small>
                <input type="url" placeholder="https://… (optional link fallback)" value={lesson.document_url} onChange={e => setLesson({ ...lesson, document_url: e.target.value })} />
              </div>
              <div className="field"><label htmlFor="lesson-content">Text content</label><textarea id="lesson-content" rows={4} value={lesson.content} onChange={e => setLesson({ ...lesson, content: e.target.value })} /></div>
            </>}
            {lesson.lesson_type === 'coding' && <>
              <div className="field"><label htmlFor="lesson-lang">Language *</label><select id="lesson-lang" value={lesson.coding_language} onChange={e => setLesson({ ...lesson, coding_language: e.target.value })}>{CODING_LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}</select></div>
              <div className="field"><label htmlFor="lesson-boiler">Boilerplate code</label><textarea id="lesson-boiler" rows={4} value={lesson.coding_boilerplate} onChange={e => setLesson({ ...lesson, coding_boilerplate: e.target.value })} /></div>
              <div className="field"><label htmlFor="lesson-expected">Expected output</label><textarea id="lesson-expected" rows={3} value={lesson.coding_expected_output} onChange={e => setLesson({ ...lesson, coding_expected_output: e.target.value })} /></div>
            </>}
            <div className="field"><label><input type="checkbox" checked={lesson.is_preview} onChange={e => setLesson({ ...lesson, is_preview: e.target.checked })} /> Free preview</label></div>
            <div className="field"><label><input type="checkbox" checked={lesson.is_required} onChange={e => setLesson({ ...lesson, is_required: e.target.checked })} /> Required for course completion</label></div>
            <button className="btn btn-primary" disabled={busy}>{busy ? 'Adding…' : 'Add lesson to this unit'}</button>{' '}
            <button type="button" className="btn btn-soft" onClick={() => { setTargetUnit(null); setAddKind(''); }}>Done</button>
          </form>}

          {targetUnit === u.id && (addKind === 'quiz' || addKind === 'final' || addKind === 'assignment') && <form onSubmit={saveContent}>
            {addKind === 'assignment' ? <>
              <div className="field"><label htmlFor="asg-title">Assignment title *</label><input id="asg-title" required value={asg.title} onChange={e => setAsg({ ...asg, title: e.target.value })} /></div>
              <div className="field"><label htmlFor="asg-inst">Instructions *</label><textarea id="asg-inst" rows={3} required value={asg.instructions} onChange={e => setAsg({ ...asg, instructions: e.target.value })} /></div>
              <div className="field"><label htmlFor="asg-due">Due date (optional)</label><input id="asg-due" type="datetime-local" value={asg.due_at} onChange={e => setAsg({ ...asg, due_at: e.target.value })} /></div>
              <div className="field"><label htmlFor="asg-points">Points</label><input id="asg-points" type="number" min="1" value={asg.max_points} onChange={e => setAsg({ ...asg, max_points: Number(e.target.value) })} /></div>
              <div className="field"><label htmlFor="asg-rubric">Rubric</label><textarea id="asg-rubric" rows={2} value={asg.rubric} onChange={e => setAsg({ ...asg, rubric: e.target.value })} /></div>
              <div className="field"><label htmlFor="asg-type">Accepted submission</label><select id="asg-type" value={asg.accepted_types} onChange={e => setAsg({ ...asg, accepted_types: e.target.value })}><option value="both">File or text</option><option value="file">File upload</option><option value="text">Text response</option></select></div>
              <div className="field"><label><input type="checkbox" checked={asg.is_required} onChange={e => setAsg({ ...asg, is_required: e.target.checked })} /> Required for course completion</label></div>
            </> : <>
              <div className="field"><label htmlFor="quiz-title">{addKind === 'final' ? 'Final exam title *' : 'Quiz title *'}</label><input id="quiz-title" required value={quizTitle} onChange={e => setQuizTitle(e.target.value)} /></div>
              <div className="field"><label htmlFor="pass">Pass mark (%)</label><input id="pass" type="number" min="1" max="100" required value={passPercentage} onChange={e => setPassPercentage(Number(e.target.value))} /></div>
              {questions.map((q, i) => <fieldset key={i} className="panel"><legend>Question {i + 1}</legend>
                <div className="field"><label htmlFor={`question-${i}`}>Question</label><textarea id={`question-${i}`} required rows={2} value={q.question} onChange={e => setQuestions(questions.map((x, j) => j === i ? { ...x, question: e.target.value } : x))} /></div>
                {(['a', 'b', 'c', 'd'] as const).map(key => <div className="field" key={key}><label htmlFor={`option-${i}-${key}`}>Option {key.toUpperCase()}</label><input id={`option-${i}-${key}`} required value={q[`option_${key}`]} onChange={e => setQuestions(questions.map((x, j) => j === i ? { ...x, [`option_${key}`]: e.target.value } : x))} /></div>)}
                <div className="field"><label htmlFor={`answer-${i}`}>Correct answer</label><select id={`answer-${i}`} value={q.correct_answer} onChange={e => setQuestions(questions.map((x, j) => j === i ? { ...x, correct_answer: e.target.value } : x))}><option value="a">Option A</option><option value="b">Option B</option><option value="c">Option C</option><option value="d">Option D</option></select></div>
                {questions.length > 1 && <button type="button" className="btn btn-soft" onClick={() => setQuestions(questions.filter((_, j) => j !== i))}>Remove question</button>}
              </fieldset>)}
              <button type="button" className="btn btn-soft" onClick={() => setQuestions([...questions, blankQ()])}>+ Add question</button>{' '}
            </>}
            <button className="btn btn-primary" disabled={busy}>{busy ? 'Adding…' : addKind === 'assignment' ? 'Add assignment' : addKind === 'final' ? 'Add final exam' : 'Add quiz'}</button>{' '}
            <button type="button" className="btn btn-soft" onClick={() => { setTargetUnit(null); setAddKind(''); }}>Done</button>
          </form>}

          <div style={{ marginTop: 12 }}>
            <button className="btn btn-soft" onClick={() => void removeUnit(u.id, u.title)}>Delete unit</button>
          </div>
        </div>)}

        <div className="panel">
          <h3>Add a unit</h3>
          <form onSubmit={saveUnit} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'end' }}>
            <div className="field" style={{ flex: '1 1 240px', margin: 0 }}>
              <label htmlFor="unit-title">Unit title</label>
              <input id="unit-title" value={unitTitle} onChange={e => setUnitTitle(e.target.value)} placeholder="e.g. Getting started" />
            </div>
            <button className="btn btn-primary" disabled={busy}>{busy ? 'Adding…' : 'Add unit'}</button>
          </form>
        </div>

        <div className="panel">
          <h3>Quizzes, assignments &amp; final exam in this course</h3>
          {quizzes.length === 0 && assignments.length === 0 && <p className="muted">Nothing added yet — use the “Add to this unit” dropdown inside a unit above.</p>}
          {quizzes.map(q => <div className="problem-row" key={`q-${q.id}`}><div><b>{q.title}{q.is_final ? ' — Final exam' : ''}</b><small className="muted">{q.questions.length} question(s) · pass {q.pass_percentage}%{q.is_final ? ' · monitored · gates the certificate' : ''}</small></div><span><button className="btn btn-soft" onClick={() => void removeContent('quiz', q.id)}>Delete</button></span></div>)}
          {assignments.map(a => <div className="problem-row" key={`a-${a.id}`}><div><b>{a.title} — Assignment</b><small className="muted">{a.max_points} points{a.due_at ? ` · due ${new Date(a.due_at).toLocaleString()}` : ''}</small></div><span><button className="btn btn-soft" onClick={() => void removeContent('assignment', a.id)}>Delete</button></span></div>)}
          <p className="muted">Quizzes, assignments and the final exam belong to the course, not to one unit — that is how the API stores them — so they are listed here together, even though you add them from inside a unit.</p>
        </div>

        <div className="panel">
          <h3>Step 3 — Submit for admin review</h3>
          <p className="muted">This is the only step that sends the course to an admin. Until you press it, the course is just your draft — learners cannot see it, and no admin review is opened.</p>
          <ul>
            <li>{units.length > 0 ? '✓' : '○'} At least one unit — {units.length} added</li>
            <li>{lessonCount > 0 ? '✓' : '○'} At least one lesson — {lessonCount} added</li>
            <li>{existingFinal ? '✓' : '○'} Final exam — {existingFinal ? `“${existingFinal.title}”` : 'not added (optional)'}</li>
          </ul>
          <p className="muted">Note: the course status has read “pending” since Step 1 — that is how the platform has always stored a new course, and it does not put it in front of an admin. Pressing Submit creates the review record the admin queue works from; you will land on the confirmation page.</p>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button className="btn btn-primary" disabled={busy || !canSubmit} onClick={submitReview}>Submit for admin review</button>
            <a className="btn btn-soft" href="/instructor/courses">Finish later — My courses</a>
            <a className="btn btn-soft" href={`/instructor/courses/${created.id}`}>Open full course editor</a>
          </div>
          {!canSubmit && <p className="muted" style={{ marginTop: 8 }}>Add at least one unit and one lesson first — the review endpoint requires both.</p>}
        </div>
      </>}
    </div>
  </PortalShell>;
}
