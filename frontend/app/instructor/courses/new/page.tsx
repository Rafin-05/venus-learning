'use client';
import { FormEvent, useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import PortalShell from '../../../../components/PortalShell';
import AssetUpload from '../../../../components/AssetUpload';
import { api, list, post } from '../../../../lib/api';

// Rebuilt course creation: one straightforward page, no steps. Create the
// course, then add its content on the same page with one dropdown — quiz,
// assignment, or final exam — instead of separate flows for each. Video and
// document lessons still live on the course editor
// (/instructor/courses/[id]), which is linked from here once the course
// exists. No backend change: every form below posts to an existing endpoint
// with the payload that endpoint already accepts.
type Question = { question: string; option_a: string; option_b: string; option_c: string; option_d: string; correct_answer: string };
type QuizItem = { id: number; title: string; is_final: boolean; pass_percentage: number; questions: Question[] };
type AssignmentItem = { id: number; title: string; max_points: number; due_at?: string | null };
type CreatedCourse = { id: number; title: string; status?: string };

const blankQ = (): Question => ({ question: '', option_a: '', option_b: '', option_c: '', option_d: '', correct_answer: 'a' });

export default function NewCourse() {
  const router = useRouter();
  const [f, setF] = useState({
    title: '', subtitle: '', description: '', category: '', subcategory: '',
    level: '', language: 'en', thumbnail: '', promo_video_url: '',
    outcomesText: '', target_audience: '', prerequisites: '',
    is_free: true, price: '0.00', enrollment_open: true,
    access_duration_days: '', completion_threshold: 90,
  });
  const [created, setCreated] = useState<CreatedCourse | null>(null);
  const [contentType, setContentType] = useState<'quiz' | 'assignment' | 'final'>('quiz');
  const [quizTitle, setQuizTitle] = useState('');
  const [passPercentage, setPassPercentage] = useState(70);
  const [questions, setQuestions] = useState<Question[]>([blankQ()]);
  const [asg, setAsg] = useState({ title: '', instructions: '', due_at: '', max_points: 100, rubric: '', accepted_types: 'both', is_required: false });
  const [quizzes, setQuizzes] = useState<QuizItem[]>([]);
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);

  const existingFinal = quizzes.find(q => q.is_final);
  const outcomes = f.outcomesText.split('\n').map(s => s.trim()).filter(Boolean);

  const loadContent = useCallback(async (courseId: number) => {
    try {
      const [q, a] = await Promise.all([api(`/quizzes/?course=${courseId}`), api(`/assignments/?course=${courseId}`)]);
      setQuizzes(list(q)); setAssignments(list(a));
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load course content.'); }
  }, []);

  useEffect(() => { if (created) void loadContent(created.id); }, [created, loadContent]);

  const createCourse = async (e: FormEvent) => {
    e.preventDefault();
    if (!f.title.trim() || !f.description.trim()) { setError('Title and description are required.'); return; }
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
      setNotice(`Course “${c.title}” created as a draft. Add content below, then submit it for admin review.`);
    } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  const saveContent = async (e: FormEvent) => {
    e.preventDefault();
    if (!created) return;
    setError(''); setNotice('');
    if (contentType === 'assignment') {
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
        await loadContent(created.id);
      } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
      return;
    }
    // Quiz or final exam: same quiz endpoint, is_final set for the final.
    const isFinal = contentType === 'final';
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
      await loadContent(created.id);
    } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  const removeContent = async (kind: 'quiz' | 'assignment', id: number) => {
    if (!created || !window.confirm('Delete this item? This cannot be undone.')) return;
    setBusy(true);
    try { await api(kind === 'quiz' ? `/quizzes/${id}/` : `/assignments/${id}/`, { method: 'DELETE' }); await loadContent(created.id); }
    catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  const submitReview = async () => {
    if (!created) return;
    setBusy(true); setError('');
    try {
      await post(`/courses/${created.id}/submit-review/`, {});
      router.push(`/instructor/courses/${created.id}/review-submitted`);
    } catch (x) { setError((x as Error).message); } finally { setBusy(false); }
  };

  return <PortalShell title="Create course" role="Instructor">
    <div className="panel">
      <h2>{created ? `Course: ${created.title}` : 'New course'}</h2>
      <p className="muted">{created
        ? 'Your course is a draft — learners cannot see it until an administrator approves it. Add content below, then submit it for review.'
        : 'Fill in the course on this one page and create it. No steps — everything is here.'}</p>
      {error && <div className="form-error" role="alert">{error}</div>}
      {notice && <p className="success">{notice}</p>}

      {!created && <form onSubmit={createCourse}>
        <h3>Course details</h3>
        <div className="field"><label htmlFor="title">Course title *</label><input id="title" required value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /></div>
        <div className="field"><label htmlFor="subtitle">Subtitle</label><input id="subtitle" value={f.subtitle} onChange={e => setF({ ...f, subtitle: e.target.value })} /></div>
        <div className="field"><label htmlFor="description">Detailed description *</label><textarea id="description" rows={6} required value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></div>
        <div className="field"><label htmlFor="category">Category</label><input id="category" value={f.category} onChange={e => setF({ ...f, category: e.target.value })} /></div>
        <div className="field"><label htmlFor="subcategory">Subcategory</label><input id="subcategory" value={f.subcategory} onChange={e => setF({ ...f, subcategory: e.target.value })} /></div>
        <div className="field"><label htmlFor="level">Level</label><select id="level" value={f.level} onChange={e => setF({ ...f, level: e.target.value })}><option value="">Choose a level</option><option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select></div>
        <div className="field"><label htmlFor="language">Language</label><input id="language" value={f.language} onChange={e => setF({ ...f, language: e.target.value })} /></div>
        <div className="field"><label>Thumbnail</label><AssetUpload purpose="thumbnail" onUploaded={url => setF({ ...f, thumbnail: url })} />
          {f.thumbnail && <img src={f.thumbnail} alt="Course thumbnail preview" style={{ width: '100%', maxWidth: 320, borderRadius: 12, marginTop: 8 }} />}
          <small className="muted">Upload an image file, or paste an image link below as a fallback.</small>
          <input type="url" placeholder="https://… (optional link fallback)" value={f.thumbnail} onChange={e => setF({ ...f, thumbnail: e.target.value })} />
        </div>
        <div className="field"><label htmlFor="promo">Promotional video (optional, YouTube link)</label><input id="promo" type="url" placeholder="https://www.youtube.com/watch?v=…" value={f.promo_video_url} onChange={e => setF({ ...f, promo_video_url: e.target.value })} /><small className="muted">The video ID is validated on the server. Unlisted videos can be embedded but are not private — anyone with the link can share it.</small></div>

        <h3>What learners will learn</h3>
        <div className="field"><label htmlFor="outcomes">Outcomes (one per line)</label><textarea id="outcomes" rows={5} value={f.outcomesText} onChange={e => setF({ ...f, outcomesText: e.target.value })} placeholder={'Write a Python program\nUse lists and loops'} /></div>
        <div className="field"><label htmlFor="audience">Target audience</label><textarea id="audience" rows={3} value={f.target_audience} onChange={e => setF({ ...f, target_audience: e.target.value })} /></div>
        <div className="field"><label htmlFor="prereq">Prerequisites</label><textarea id="prereq" rows={3} value={f.prerequisites} onChange={e => setF({ ...f, prerequisites: e.target.value })} /></div>

        <h3>Pricing &amp; access</h3>
        <div className="field"><label><input type="checkbox" checked={f.is_free} onChange={e => setF({ ...f, is_free: e.target.checked })} /> Free course</label></div>
        {!f.is_free && <div className="field"><label htmlFor="price">Price</label><input id="price" type="number" min="0" step="0.01" required value={f.price} onChange={e => setF({ ...f, price: e.target.value })} /><small className="muted">Payment collection is not built yet — paid courses cannot be enrolled in until a payment method is added.</small></div>}
        <div className="field"><label><input type="checkbox" checked={f.enrollment_open} onChange={e => setF({ ...f, enrollment_open: e.target.checked })} /> Enrollment open</label></div>
        <div className="field"><label htmlFor="access">Access duration (days, blank = no expiry)</label><input id="access" type="number" min="1" value={f.access_duration_days} onChange={e => setF({ ...f, access_duration_days: e.target.value })} /></div>
        <div className="field"><label htmlFor="threshold">Video completion threshold (%)</label><input id="threshold" type="number" min="1" max="100" required value={f.completion_threshold} onChange={e => setF({ ...f, completion_threshold: Number(e.target.value) })} /><small className="muted">A video lesson counts as complete once this much has been watched. Default 90%.</small></div>
        <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Create course'}</button>
      </form>}

      {created && <>
        <div className="panel">
          <h3>Add content</h3>
          <p className="muted">Pick one type, fill in its form, and add it. Quizzes and the final exam need at least one question — add as many as you need below.</p>
          <div className="field"><label htmlFor="content-type">What do you want to add?</label>
            <select id="content-type" value={contentType} onChange={e => setContentType(e.target.value as 'quiz' | 'assignment' | 'final')}>
              <option value="quiz">Quiz</option>
              <option value="assignment">Assignment</option>
              <option value="final" disabled={!!existingFinal}>Final exam{existingFinal ? ' — already set' : ''}</option>
            </select>
            {contentType === 'final' && <small className="muted">Only one final exam per course. It appears after all lessons, is taken only with camera monitoring, and passing it unlocks the certificate.{existingFinal ? ` This course already has one (“${existingFinal.title}”).` : ''}</small>}
          </div>
          <form onSubmit={saveContent}>
            {contentType === 'assignment' ? <>
              <div className="field"><label htmlFor="asg-title">Assignment title *</label><input id="asg-title" required value={asg.title} onChange={e => setAsg({ ...asg, title: e.target.value })} /></div>
              <div className="field"><label htmlFor="asg-inst">Instructions *</label><textarea id="asg-inst" rows={3} required value={asg.instructions} onChange={e => setAsg({ ...asg, instructions: e.target.value })} /></div>
              <div className="field"><label htmlFor="asg-due">Due date (optional)</label><input id="asg-due" type="datetime-local" value={asg.due_at} onChange={e => setAsg({ ...asg, due_at: e.target.value })} /></div>
              <div className="field"><label htmlFor="asg-points">Points</label><input id="asg-points" type="number" min="1" value={asg.max_points} onChange={e => setAsg({ ...asg, max_points: Number(e.target.value) })} /></div>
              <div className="field"><label htmlFor="asg-rubric">Rubric</label><textarea id="asg-rubric" rows={2} value={asg.rubric} onChange={e => setAsg({ ...asg, rubric: e.target.value })} /></div>
              <div className="field"><label htmlFor="asg-type">Accepted submission</label><select id="asg-type" value={asg.accepted_types} onChange={e => setAsg({ ...asg, accepted_types: e.target.value })}><option value="both">File or text</option><option value="file">File upload</option><option value="text">Text response</option></select></div>
              <div className="field"><label><input type="checkbox" checked={asg.is_required} onChange={e => setAsg({ ...asg, is_required: e.target.checked })} /> Required for course completion</label></div>
            </> : <>
              <div className="field"><label htmlFor="quiz-title">{contentType === 'final' ? 'Final exam title *' : 'Quiz title *'}</label><input id="quiz-title" required value={quizTitle} onChange={e => setQuizTitle(e.target.value)} /></div>
              <div className="field"><label htmlFor="pass">Pass mark (%)</label><input id="pass" type="number" min="1" max="100" required value={passPercentage} onChange={e => setPassPercentage(Number(e.target.value))} /></div>
              {questions.map((q, i) => <fieldset key={i} className="panel"><legend>Question {i + 1}</legend>
                <div className="field"><label htmlFor={`question-${i}`}>Question</label><textarea id={`question-${i}`} required rows={2} value={q.question} onChange={e => setQuestions(questions.map((x, j) => j === i ? { ...x, question: e.target.value } : x))} /></div>
                {(['a', 'b', 'c', 'd'] as const).map(key => <div className="field" key={key}><label htmlFor={`option-${i}-${key}`}>Option {key.toUpperCase()}</label><input id={`option-${i}-${key}`} required value={q[`option_${key}`]} onChange={e => setQuestions(questions.map((x, j) => j === i ? { ...x, [`option_${key}`]: e.target.value } : x))} /></div>)}
                <div className="field"><label htmlFor={`answer-${i}`}>Correct answer</label><select id={`answer-${i}`} value={q.correct_answer} onChange={e => setQuestions(questions.map((x, j) => j === i ? { ...x, correct_answer: e.target.value } : x))}><option value="a">Option A</option><option value="b">Option B</option><option value="c">Option C</option><option value="d">Option D</option></select></div>
                {questions.length > 1 && <button type="button" className="btn btn-soft" onClick={() => setQuestions(questions.filter((_, j) => j !== i))}>Remove question</button>}
              </fieldset>)}
              <button type="button" className="btn btn-soft" onClick={() => setQuestions([...questions, blankQ()])}>+ Add question</button>{' '}
            </>}
            <button className="btn btn-primary" disabled={busy}>{busy ? 'Adding…' : contentType === 'assignment' ? 'Add assignment' : contentType === 'final' ? 'Add final exam' : 'Add quiz'}</button>
          </form>
        </div>

        <div className="panel">
          <h3>Added to this course</h3>
          {quizzes.length === 0 && assignments.length === 0 && <p className="muted">Nothing added yet.</p>}
          {quizzes.map(q => <div className="problem-row" key={`q-${q.id}`}><div><b>{q.title}{q.is_final ? ' — Final exam' : ''}</b><small className="muted">{q.questions.length} question(s) · pass {q.pass_percentage}%{q.is_final ? ' · monitored · gates the certificate' : ''}</small></div><span><button className="btn btn-soft" onClick={() => void removeContent('quiz', q.id)}>Delete</button></span></div>)}
          {assignments.map(a => <div className="problem-row" key={`a-${a.id}`}><div><b>{a.title} — Assignment</b><small className="muted">{a.max_points} points{a.due_at ? ` · due ${new Date(a.due_at).toLocaleString()}` : ''}</small></div><span><button className="btn btn-soft" onClick={() => void removeContent('assignment', a.id)}>Delete</button></span></div>)}
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 16 }}>
          <button className="btn btn-primary" disabled={busy} onClick={submitReview}>Submit for admin review</button>
          <a className="btn btn-soft" href={`/instructor/courses/${created.id}`}>Add video / document lessons →</a>
          <a className="btn btn-soft" href="/instructor/courses">My courses</a>
        </div>
        <p className="muted" style={{ marginTop: 8 }}>Video and document lessons are added on the course editor, linked above. Submitting sends the course to an administrator — it stays Pending until approved, and you will land on the confirmation page.</p>
      </>}
    </div>
  </PortalShell>;
}
