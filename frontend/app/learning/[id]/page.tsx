'use client';

import Link from 'next/link';
import {useParams} from 'next/navigation';
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {api, all, list, patch, post} from '../../../lib/api';
import {LearnerError, LearnerEmpty, LearnerLoading} from '../../../components/LearnerStates';
import AssetUpload from '../../../components/AssetUpload';

type Lesson = {id:number; title:string; description?:string; content:string; position:number; video_url?:string; provider?:string; provider_video_id?:string; document_url?:string; lesson_type:string; coding_language?:string; coding_boilerplate?:string; progress?:number; duration_seconds?:number|null; is_preview?:boolean; is_required?:boolean; watch_percentage?:number; resume_position_seconds?:number};
type Unit = {id:number; title:string; position:number; lessons:Lesson[]};
type Course = {id:number; title:string; description:string; units?:Unit[]};
type Question = {id:number; question:string; option_a:string; option_b:string; option_c?:string; option_d?:string};
type Quiz = {id:number; title:string; pass_percentage:number; questions:Question[]};
const message = (error:unknown) => error instanceof Error ? error.message : 'The request could not be completed.';
function safeLink(value?:string) {try {const url = new URL(value || '');return ['https:','http:'].includes(url.protocol) ? url.href : '';} catch {return '';}}
function youtubeEmbed(value?:string, providerVideoId?:string) {
  if (providerVideoId && /^[\w-]{11}$/.test(providerVideoId)) return `https://www.youtube-nocookie.com/embed/${providerVideoId}?enablejsapi=1`;
  try {
    const url = new URL(value || ''); if (url.protocol !== 'https:') return '';
    const host = url.hostname.toLowerCase(); let id = '';
    if (host === 'youtu.be') id = url.pathname.slice(1).split('/')[0];
    if (['www.youtube.com','youtube.com','www.youtube-nocookie.com'].includes(host)) id = url.searchParams.get('v') || url.pathname.match(/^\/(?:embed|shorts)\/([\w-]+)/)?.[1] || '';
    return /^[\w-]{11}$/.test(id) ? `https://www.youtube-nocookie.com/embed/${id}?enablejsapi=1` : '';
  } catch {return '';}
}
declare global { interface Window { YT?: any; onYouTubeIframeAPIReady?: () => void; } }

export default function Learning() {
  const {id} = useParams<{id:string}>();
  const [course,setCourse] = useState<Course|null>(null);
  const [units,setUnits] = useState<Unit[]>([]);
  const [selectedId,setSelectedId] = useState<number|null>(null);
  const [quizzes,setQuizzes] = useState<Quiz[]>([]);
  const [answers,setAnswers] = useState<Record<number,Record<string,string>>>({});
  const [results,setResults] = useState<Record<number,any>>({});
  const [progress,setProgress] = useState<Record<number,number>>({});
  const [error,setError] = useState(''); const [loading,setLoading] = useState(true);
  const [saving,setSaving] = useState(false); const [notice,setNotice] = useState('');
  const [code,setCode] = useState(''); const [language,setLanguage] = useState('71'); const [runnerResult,setRunnerResult] = useState('');
  const [playback,setPlayback] = useState<any>(null);
  const [resources,setResources] = useState<any[]>([]);
  const [assignments,setAssignments] = useState<any[]>([]);
  const [assignmentText,setAssignmentText] = useState<Record<number,string>>({});
  const [assignmentAsset,setAssignmentAsset] = useState<Record<number,string>>({});
  const [watched,setWatched] = useState(0);
  const watchedRef = useRef<Set<number>>(new Set());
  const playerRef = useRef<any>(null);
  const timerRef = useRef<any>(null);
  const lessons = useMemo(() => units.flatMap(unit => unit.lessons || []),[units]);
  const selected = lessons.find(lesson => lesson.id === selectedId) || null;
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [curriculum,lessonResponse,quizResponse,resourceResponse,assignmentResponse] = await Promise.all([
        api(`/courses/${id}/curriculum/`), all(`/lessons/?course=${id}`), all(`/quizzes/?course=${id}`), all(`/resources/?course=${id}`), all(`/assignments/?course=${id}`)
      ]);
      const currentCourse = curriculum.course || curriculum;
      const actualLessons:Lesson[] = list(lessonResponse);
      const byId = new Map(actualLessons.map(lesson => [lesson.id,lesson]));
      const currentUnits:Unit[] = (curriculum.units || currentCourse.units || []).map((unit:Unit) => ({...unit,lessons:(unit.lessons || []).map(lesson => byId.get(lesson.id)).filter(Boolean)}));
      setCourse(currentCourse); setUnits(currentUnits); setQuizzes(list(quizResponse)); setResources(list(resourceResponse)); setAssignments(list(assignmentResponse));
      const saved:Record<number,number> = {};
      actualLessons.forEach(lesson => {saved[lesson.id] = Number(lesson.progress || 0);});
      setProgress(saved); setSelectedId(current => current || actualLessons[0]?.id || null);
    } catch (err) {setError(message(err));} finally {setLoading(false);}
  },[id]);
  useEffect(() => {void load();},[load]);
  useEffect(() => {setCode(selected?.coding_boilerplate || '');setLanguage(({python:'71',javascript:'63',java:'62',cpp:'54','c++':'54',c:'50',go:'60',rust:'73'} as Record<string,string>)[String(selected?.coding_language).toLowerCase()] || selected?.coding_language || '71');setRunnerResult('');setNotice('');},[selectedId]);

  // PDF §6/§7: ask the backend for the embed identifier (enrollment is
  // checked server-side), then track actual playback with the YouTube
  // IFrame Player API — watched seconds, resume position and completion
  // at the course threshold. Paused time is not counted, and replayed
  // seconds are not double-counted.
  const sendProgress = useCallback(async (lessonId:number, extra:Record<string,number|undefined>) => {
    try {
      const result = await patch<{progress:number;watch_percentage:number}>(`/lessons/${lessonId}/progress/`, extra);
      setProgress(old => ({...old,[lessonId]:result.progress}));
      return result;
    } catch { return null; }
  }, []);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    watchedRef.current = new Set();
    setWatched(0);
    setPlayback(null);
    if (playerRef.current) { try { playerRef.current.destroy(); } catch { /* already gone */ } playerRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    api(`/lessons/${selected.id}/playback/`).then(data => { if (active) { setPlayback(data); setWatched(Math.round((data.watch_percentage || 0) * (data.duration_seconds || selected.duration_seconds || 0) / 100)); } }).catch(() => { if (active) setPlayback({ embed_url: youtubeEmbed(selected.video_url, selected.provider_video_id), duration_seconds: selected.duration_seconds, resume_position_seconds: selected.resume_position_seconds || 0, watch_percentage: selected.watch_percentage || 0, completion_threshold: 90 }); });
    return () => { active = false; if (timerRef.current) clearInterval(timerRef.current); };
  }, [selectedId]);

  useEffect(() => {
    if (!playback?.embed_url || !selected || selected.lesson_type !== 'video') return;
    const startPlayer = () => {
      if (!window.YT || !window.YT.Player) return;
      const duration = playback.duration_seconds || selected.duration_seconds || 0;
      playerRef.current = new window.YT.Player('lesson-player', {
        events: {
          onReady: (event:any) => { const resume = playback.resume_position_seconds || 0; if (resume > 0) event.target.seekTo(resume, true); },
          onStateChange: (event:any) => {
            const YT = window.YT;
            if (event.data === YT.PlayerState.PLAYING) {
              if (timerRef.current) clearInterval(timerRef.current);
              timerRef.current = setInterval(() => {
                try {
                  const player = playerRef.current; if (!player) return;
                  const current = Math.floor(player.getCurrentTime() || 0);
                  const dur = Math.floor(player.getDuration() || duration || 0);
                  watchedRef.current.add(current);
                  const total = watchedRef.current.size;
                  setWatched(total);
                  if (total % 15 === 0) void sendProgress(selected.id, { watched_seconds: total, duration_seconds: dur || undefined, resume_position_seconds: current });
                } catch { /* player not ready */ }
              }, 1000);
            } else {
              if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
              if (event.data === YT.PlayerState.PAUSED || event.data === YT.PlayerState.ENDED) {
                try {
                  const player = playerRef.current; if (!player) return;
                  const current = Math.floor(player.getCurrentTime() || 0);
                  const dur = Math.floor(player.getDuration() || duration || 0);
                  void sendProgress(selected.id, { watched_seconds: watchedRef.current.size, duration_seconds: dur || undefined, resume_position_seconds: current });
                } catch { /* ignore */ }
              }
            }
          },
        },
      });
    };
    if (window.YT?.Player) { startPlayer(); return; }
    const tag = document.createElement('script');
    tag.src = 'https://www.youtube.com/iframe_api';
    document.body.appendChild(tag);
    window.onYouTubeIframeAPIReady = () => startPlayer();
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [playback?.embed_url, selectedId]);

  async function complete() {
    if (!selected || selected.lesson_type === 'coding') return;
    setSaving(true);setNotice('');
    try {
      if (selected.lesson_type === 'video') {
        const threshold = playback?.completion_threshold ?? 90;
        const duration = playback?.duration_seconds || selected.duration_seconds || 0;
        const pct = duration ? Math.min(100, Math.round(watched * 100 / duration)) : (playback?.watch_percentage || 0);
        if (pct < threshold) { setNotice(`Watch ${threshold}% of this video to complete it — you are at ${pct}%.`); return; }
        const result = await sendProgress(selected.id, { watched_seconds: watched, duration_seconds: duration || undefined, resume_position_seconds: playback?.resume_position_seconds || 0 });
        if (result) setNotice('Lesson progress saved.');
      } else {
        const result = await patch<{progress:number}>(`/lessons/${selected.id}/progress/`,{progress:100});
        setProgress(old => ({...old,[selected.id]:result.progress}));setNotice('Lesson progress saved.');
      }
      const index = lessons.findIndex(lesson => lesson.id === selected.id);
      if (lessons[index+1]) setSelectedId(lessons[index+1].id);
    } catch (err) {setNotice(message(err));} finally {setSaving(false);}
  }

  async function submitAssignment(assignment:any) {
    const text = (assignmentText[assignment.id] || '').trim();
    const asset = assignmentAsset[assignment.id] || '';
    if (assignment.accepted_types === 'file' && !asset) { setNotice('This assignment requires a file upload.'); return; }
    if (assignment.accepted_types === 'text' && !text) { setNotice('This assignment requires a text response.'); return; }
    if (!asset && !text) { setNotice('Upload a file or enter a text response.'); return; }
    setSaving(true); setNotice('');
    try {
      await post('/assignment-submissions/', { assignment: assignment.id, text_response: text, asset: asset || null });
      setNotice('Assignment submitted.');
      setAssignmentText(old => ({ ...old, [assignment.id]: '' }));
      setAssignmentAsset(old => ({ ...old, [assignment.id]: '' }));
    } catch (err) { setNotice(message(err)); } finally { setSaving(false); }
  }
  async function runCode() {
    if (!selected) return;setSaving(true);setRunnerResult('');
    try {
      const result = await post(`/lessons/${selected.id}/run/`,{code,language_id:Number(language)});
      setRunnerResult(typeof result.output === 'string' ? result.output : JSON.stringify(result,null,2));
      if (result.passed) {setProgress(old => ({...old,[selected.id]:100}));setNotice('Challenge passed. Lesson completion saved.');}
      else setNotice('The challenge has not passed. Review the execution result and try again.');
    } catch (err) {setRunnerResult(message(err));} finally {setSaving(false);}
  }
  async function submitQuiz(quiz:Quiz) {
    setSaving(true);setNotice('');
    try {const result = await post(`/quizzes/${quiz.id}/submit/`,{answers:answers[quiz.id] || {}});setResults(old => ({...old,[quiz.id]:result}));}
    catch (err) {setNotice(message(err));} finally {setSaving(false);}
  }
  if (loading) return <main className="learn-page"><LearnerLoading label="Loading your course…"/></main>;
  if (error || !course) return <main className="learn-page"><LearnerError message={error || 'Course not found.'} retry={load}/><p><Link href={`/courses/${id}`}>Course overview and enrollment</Link></p></main>;
  const embed = playback?.embed_url || youtubeEmbed(selected?.video_url, selected?.provider_video_id); const index = lessons.findIndex(lesson => lesson.id === selectedId);
  const videoDuration = playback?.duration_seconds || selected?.duration_seconds || 0;
  const videoPct = videoDuration ? Math.min(100, Math.round(watched * 100 / videoDuration)) : (playback?.watch_percentage || selected?.watch_percentage || 0);
  return <main className="learn-page">
    <div className="learn-top"><Link href={`/courses/${id}`}>← Course overview</Link><span>{course.title}</span><b>{Object.values(progress).filter(value => value === 100).length} / {lessons.length} complete</b></div>
    <div className="learn-layout"><aside className="lesson-nav"><h3>Course contents</h3>
      {units.map(unit => <div key={unit.id}><p className="muted">{unit.title}</p>{unit.lessons.map((lesson,number) => <button className={selectedId === lesson.id ? 'selected' : ''} onClick={() => setSelectedId(lesson.id)} key={lesson.id}><i>{progress[lesson.id] === 100 ? '✓' : number+1}</i>{lesson.title}<small>{progress[lesson.id] === 100 ? 'Complete' : lesson.lesson_type}</small></button>)}</div>)}
      <p><Link href="/certificates">Your certificates →</Link></p>
    </aside><article className="lesson-content">{selected ? <>
      <span className="tag">Lesson {index+1} · {selected.lesson_type}</span><h1>{selected.title}</h1>
      {selected.content && <p className="lead" style={{whiteSpace:'pre-wrap'}}>{selected.content}</p>}
      {embed ? <><iframe id="lesson-player" title={selected.title} src={embed} allow="fullscreen; encrypted-media; picture-in-picture" referrerPolicy="strict-origin-when-cross-origin" sandbox="allow-scripts allow-same-origin allow-presentation" style={{width:'100%',aspectRatio:'16 / 9',border:0,borderRadius:14}} allowFullScreen/>{selected.lesson_type === 'video' && <p className="muted">Watched {videoPct}%{videoDuration ? ` · resumes where you left off` : ''} · complete at {playback?.completion_threshold ?? 90}% watched.</p>}</> : safeLink(selected.video_url) && <p><a href={safeLink(selected.video_url)} target="_blank" rel="noopener noreferrer" className="text-link">Open lesson video ↗</a></p>}
      {safeLink(selected.document_url) && <p><a href={safeLink(selected.document_url)} target="_blank" rel="noopener noreferrer" className="text-link">Open lesson document ↗</a></p>}
      {selected.lesson_type === 'coding' ? <section className="panel" style={{padding:20,marginTop:20}}><h2>Practice this lesson</h2><div className="field"><label htmlFor="coding-language">Execution language</label><select id="coding-language" value={language} onChange={event => setLanguage(event.target.value)}><option value="71">Python 3</option><option value="63">JavaScript</option><option value="54">C++</option><option value="62">Java</option><option value="50">C</option><option value="60">Go</option><option value="73">Rust</option></select></div><div className="field"><label htmlFor="lesson-code">Source code</label><textarea id="lesson-code" rows={14} spellCheck={false} value={code} onChange={event => setCode(event.target.value)} style={{fontFamily:'monospace'}} maxLength={100000}/></div><button className="btn btn-primary" disabled={saving || !code.trim()} onClick={runCode}>{saving ? 'Running…' : 'Run and check solution'}</button><p className="muted">An isolated execution service must be configured. A server error never counts as a passed solution.</p>{runnerResult && <pre className="code-output" style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{runnerResult}</pre>}</section> : <div className="lesson-actions"><button className="btn btn-soft" disabled={index <= 0} onClick={() => setSelectedId(lessons[index-1].id)}>← Previous</button><button className="btn btn-primary" disabled={saving} onClick={complete}>{saving ? 'Saving…' : 'Mark complete & continue →'}</button></div>}
      <p className="muted">Video progress is tracked from playback — paused time is not counted. Coding completion is awarded by the server after a passing execution.</p>
    </> : <LearnerEmpty>No lessons are available yet.</LearnerEmpty>}
    {notice && <p role="status" className="form-error">{notice}</p>}
    {quizzes.map(quiz => <section className="panel quiz-panel" style={{padding:24,marginTop:28}} key={quiz.id}><h2>{quiz.title}</h2><p className="muted">Pass mark: {quiz.pass_percentage}%. Answers are graded by the server.</p><p className="muted"><Link href={`/exams/${quiz.id}/proctored`}>Take this exam with camera monitoring →</Link></p>{quiz.questions?.map(question => <fieldset key={question.id} style={{border:'1px solid #eadfe3',padding:16,margin:'16px 0',borderRadius:12}}><legend>{question.question}</legend>{(['a','b','c','d'] as const).map(option => {const text = question[`option_${option}`];return text ? <label key={option} style={{display:'block',margin:'10px 0'}}><input type="radio" name={`quiz-${quiz.id}-question-${question.id}`} value={option} checked={answers[quiz.id]?.[String(question.id)] === option} onChange={() => setAnswers(old => ({...old,[quiz.id]:{...old[quiz.id],[String(question.id)]:option}}))}/> {text}</label> : null;})}</fieldset>)}<button className="btn btn-primary" disabled={saving || !quiz.questions?.length || quiz.questions.some(question => !answers[quiz.id]?.[String(question.id)])} onClick={() => submitQuiz(quiz)}>Submit quiz</button>{results[quiz.id] && <p role="status">{results[quiz.id].passed ? 'Passed' : 'Not yet passed'}: {results[quiz.id].score} / {results[quiz.id].total} ({Number(results[quiz.id].percentage).toFixed(1)}%)</p>}</section>)}
    {resources.length > 0 && <section className="panel" style={{padding:24,marginTop:28}}><h2>Learning resources</h2>{resources.filter(r => !r.lesson || r.lesson === selected?.id).map(r => <p key={r.id}><a href={r.download_url} target="_blank" rel="noopener noreferrer" className="text-link">{r.title}</a>{r.description ? ` — ${r.description}` : ''}</p>)}</section>}
    {assignments.length > 0 && assignments.map(a => <section className="panel" style={{padding:24,marginTop:28}} key={a.id}><h2>{a.title}</h2><p>{a.instructions}</p><p className="muted">{a.max_points} points{a.due_at ? ` · due ${new Date(a.due_at).toLocaleString()}` : ''} · {a.accepted_types === 'file' ? 'file upload' : a.accepted_types === 'text' ? 'text response' : 'file or text'}</p>{a.accepted_types !== 'file' && <div className="field"><label htmlFor={`asg-text-${a.id}`}>Your response</label><textarea id={`asg-text-${a.id}`} rows={4} value={assignmentText[a.id] || ''} onChange={e => setAssignmentText(old => ({...old,[a.id]:e.target.value}))}/></div>}{a.accepted_types !== 'text' && <AssetUpload purpose="document" course={Number(id)} onUploaded={url => setAssignmentAsset(old => ({...old,[a.id]:url.match(/\/uploads\/([0-9a-f-]{36})\/content\//)?.[1] || ''}))} />}{assignmentAsset[a.id] && <p className="muted">File attached.</p>}<button className="btn btn-primary" disabled={saving} onClick={() => void submitAssignment(a)}>Submit assignment</button></section>)}
    </article></div>
  </main>;
}
