'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import PortalShell from '../../../../components/PortalShell';
import AssetUpload from '../../../../components/AssetUpload';
import { post } from '../../../../lib/api';

// Course-creation wizard (PDF §4): basics, outcomes, pricing & access,
// then review. Curriculum (sections and lessons) is built on the course
// editor after the draft is saved. No live-class step: live classes are
// not part of this feature.
const STEPS = ['Course basics', 'Learner outcomes', 'Pricing & access', 'Review & publish'];

export default function NewCourse() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [f, setF] = useState({
    title: '', subtitle: '', description: '', category: '', subcategory: '',
    level: '', language: 'en', thumbnail: '', promo_video_url: '',
    outcomesText: '', target_audience: '', prerequisites: '',
    is_free: true, price: '0.00', enrollment_open: true,
    access_duration_days: '', completion_threshold: 90,
  });
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const outcomes = f.outcomesText.split('\n').map(s => s.trim()).filter(Boolean);
  const canNext = step === 0 ? f.title.trim() && f.description.trim()
    : step === 1 ? true
    : step === 2 ? (f.is_free || Number(f.price) > 0) && f.completion_threshold >= 1 && f.completion_threshold <= 100
    : true;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!f.title.trim() || !f.description.trim()) { setError('Title and description are required.'); return; }
    setBusy(true);
    setError('');
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
      router.push(`/instructor/courses/${c.id}`);
    } catch (x) {
      setError((x as Error).message);
    } finally { setBusy(false); }
  };

  return <PortalShell title="Create course" role="Instructor">
    <div className="panel">
      <ol className="muted" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', listStyle: 'none', padding: 0, margin: '0 0 16px' }}>
        {STEPS.map((label, i) => <li key={label} style={{ fontWeight: i === step ? 700 : 400, color: i === step ? 'inherit' : undefined }}>{i + 1}. {label}</li>)}
      </ol>
      <p className="muted">Step {step + 1} of {STEPS.length} — {STEPS[step]}. Saving creates a draft; it is not visible to learners until an administrator approves it.</p>
      {error && <div className="form-error" role="alert">{error}</div>}
      <form onSubmit={save}>
        {step === 0 && <>
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
        </>}
        {step === 1 && <>
          <div className="field"><label htmlFor="outcomes">What learners will learn (one outcome per line)</label><textarea id="outcomes" rows={5} value={f.outcomesText} onChange={e => setF({ ...f, outcomesText: e.target.value })} placeholder={'Write a Python program\nUse lists and loops'} /></div>
          <div className="field"><label htmlFor="audience">Target audience</label><textarea id="audience" rows={3} value={f.target_audience} onChange={e => setF({ ...f, target_audience: e.target.value })} /></div>
          <div className="field"><label htmlFor="prereq">Prerequisites</label><textarea id="prereq" rows={3} value={f.prerequisites} onChange={e => setF({ ...f, prerequisites: e.target.value })} /></div>
        </>}
        {step === 2 && <>
          <div className="field"><label><input type="checkbox" checked={f.is_free} onChange={e => setF({ ...f, is_free: e.target.checked })} /> Free course</label></div>
          {!f.is_free && <div className="field"><label htmlFor="price">Price</label><input id="price" type="number" min="0" step="0.01" required value={f.price} onChange={e => setF({ ...f, price: e.target.value })} /><small className="muted">Payment collection is not built yet — paid courses cannot be enrolled in until a payment method is added.</small></div>}
          <div className="field"><label><input type="checkbox" checked={f.enrollment_open} onChange={e => setF({ ...f, enrollment_open: e.target.checked })} /> Enrollment open</label></div>
          <div className="field"><label htmlFor="access">Access duration (days, blank = no expiry)</label><input id="access" type="number" min="1" value={f.access_duration_days} onChange={e => setF({ ...f, access_duration_days: e.target.value })} /></div>
          <div className="field"><label htmlFor="threshold">Video completion threshold (%)</label><input id="threshold" type="number" min="1" max="100" required value={f.completion_threshold} onChange={e => setF({ ...f, completion_threshold: Number(e.target.value) })} /><small className="muted">A video lesson counts as complete once this much has been watched. Default 90%.</small></div>
        </>}
        {step === 3 && <div className="panel">
          <h2>Check before saving</h2>
          <ul>
            <li><b>{f.title || '(no title)'}</b>{f.subtitle ? ` — ${f.subtitle}` : ''}</li>
            <li>{f.category}{f.subcategory ? ` / ${f.subcategory}` : ''}{f.level ? ` · ${f.level}` : ''} · {f.language}</li>
            <li>{outcomes.length} outcome(s) listed</li>
            <li>{f.is_free ? 'Free' : `Paid — ${f.price}`} · enrollment {f.enrollment_open ? 'open' : 'closed'} · completion threshold {f.completion_threshold}%</li>
            <li>After saving, add sections and lessons on the course editor, then submit the course for admin review.</li>
          </ul>
        </div>}
        <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
          {step > 0 && <button type="button" className="btn btn-soft" onClick={() => setStep(step - 1)}>← Back</button>}
          {step < STEPS.length - 1 && <button type="button" className="btn btn-primary" disabled={!canNext} onClick={() => setStep(step + 1)}>Next →</button>}
          {step === STEPS.length - 1 && <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Create draft'}</button>}
        </div>
      </form>
    </div>
  </PortalShell>;
}
