'use client';

import Link from 'next/link';
import {useParams} from 'next/navigation';
import {useCallback, useEffect, useMemo, useState} from 'react';
import {api, all, list, patch, post} from '../../../lib/api';
import {LearnerError, LearnerEmpty, LearnerLoading} from '../../../components/LearnerStates';

type Lesson = {id:number; title:string; content:string; position:number; video_url?:string; document_url?:string; lesson_type:string; coding_language?:string; coding_boilerplate?:string; progress?:number};
type Unit = {id:number; title:string; position:number; lessons:Lesson[]};
type Course = {id:number; title:string; description:string; units?:Unit[]};
type Question = {id:number; question:string; option_a:string; option_b:string; option_c?:string; option_d?:string};
type Quiz = {id:number; title:string; pass_percentage:number; questions:Question[]};
const message = (error:unknown) => error instanceof Error ? error.message : 'The request could not be completed.';
function safeLink(value?:string) {try {const url = new URL(value || '');return ['https:','http:'].includes(url.protocol) ? url.href : '';} catch {return '';}}
function youtubeEmbed(value?:string) {
  try {
    const url = new URL(value || ''); if (url.protocol !== 'https:') return '';
    const host = url.hostname.toLowerCase(); let id = '';
    if (host === 'youtu.be') id = url.pathname.slice(1).split('/')[0];
    if (['www.youtube.com','youtube.com','www.youtube-nocookie.com'].includes(host)) id = url.searchParams.get('v') || url.pathname.match(/^\/(?:embed|shorts)\/([\w-]+)/)?.[1] || '';
    return /^[\w-]{11}$/.test(id) ? `https://www.youtube-nocookie.com/embed/${id}` : '';
  } catch {return '';}
}

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
  const lessons = useMemo(() => units.flatMap(unit => unit.lessons || []),[units]);
  const selected = lessons.find(lesson => lesson.id === selectedId) || null;
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [curriculum,lessonResponse,quizResponse] = await Promise.all([
        api(`/courses/${id}/curriculum/`), all(`/lessons/?course=${id}`), all(`/quizzes/?course=${id}`)
      ]);
      const currentCourse = curriculum.course || curriculum;
      const actualLessons:Lesson[] = list(lessonResponse);
      const byId = new Map(actualLessons.map(lesson => [lesson.id,lesson]));
      const currentUnits:Unit[] = (curriculum.units || currentCourse.units || []).map((unit:Unit) => ({...unit,lessons:(unit.lessons || []).map(lesson => byId.get(lesson.id)).filter(Boolean)}));
      setCourse(currentCourse); setUnits(currentUnits); setQuizzes(list(quizResponse));
      const saved:Record<number,number> = {};
      actualLessons.forEach(lesson => {saved[lesson.id] = Number(lesson.progress || 0);});
      setProgress(saved); setSelectedId(current => current || actualLessons[0]?.id || null);
    } catch (err) {setError(message(err));} finally {setLoading(false);}
  },[id]);
  useEffect(() => {void load();},[load]);
  useEffect(() => {setCode(selected?.coding_boilerplate || '');setLanguage(({python:'71',javascript:'63',java:'62',cpp:'54','c++':'54',c:'50',go:'60',rust:'73'} as Record<string,string>)[String(selected?.coding_language).toLowerCase()] || selected?.coding_language || '71');setRunnerResult('');setNotice('');},[selectedId]);

  async function complete() {
    if (!selected || selected.lesson_type === 'coding') return;
    setSaving(true);setNotice('');
    try {
      const result = await patch<{progress:number}>(`/lessons/${selected.id}/progress/`,{progress:100});
      setProgress(old => ({...old,[selected.id]:result.progress}));setNotice('Lesson progress saved.');
      const index = lessons.findIndex(lesson => lesson.id === selected.id);
      if (lessons[index+1]) setSelectedId(lessons[index+1].id);
    } catch (err) {setNotice(message(err));} finally {setSaving(false);}
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
  const embed = youtubeEmbed(selected?.video_url); const index = lessons.findIndex(lesson => lesson.id === selectedId);
  return <main className="learn-page">
    <div className="learn-top"><Link href={`/courses/${id}`}>← Course overview</Link><span>{course.title}</span><b>{Object.values(progress).filter(value => value === 100).length} / {lessons.length} complete</b></div>
    <div className="learn-layout"><aside className="lesson-nav"><h3>Course contents</h3>
      {units.map(unit => <div key={unit.id}><p className="muted">{unit.title}</p>{unit.lessons.map((lesson,number) => <button className={selectedId === lesson.id ? 'selected' : ''} onClick={() => setSelectedId(lesson.id)} key={lesson.id}><i>{progress[lesson.id] === 100 ? '✓' : number+1}</i>{lesson.title}<small>{progress[lesson.id] === 100 ? 'Complete' : lesson.lesson_type}</small></button>)}</div>)}
      <p><Link href="/certificates">Your certificates →</Link></p>
    </aside><article className="lesson-content">{selected ? <>
      <span className="tag">Lesson {index+1} · {selected.lesson_type}</span><h1>{selected.title}</h1>
      {selected.content && <p className="lead" style={{whiteSpace:'pre-wrap'}}>{selected.content}</p>}
      {embed ? <iframe title={selected.title} src={embed} allow="fullscreen; encrypted-media; picture-in-picture" referrerPolicy="strict-origin-when-cross-origin" sandbox="allow-scripts allow-same-origin allow-presentation" style={{width:'100%',aspectRatio:'16 / 9',border:0,borderRadius:14}} allowFullScreen/> : safeLink(selected.video_url) && <p><a href={safeLink(selected.video_url)} target="_blank" rel="noopener noreferrer" className="text-link">Open lesson video ↗</a></p>}
      {safeLink(selected.document_url) && <p><a href={safeLink(selected.document_url)} target="_blank" rel="noopener noreferrer" className="text-link">Open lesson document ↗</a></p>}
      {selected.lesson_type === 'coding' ? <section className="panel" style={{padding:20,marginTop:20}}><h2>Practice this lesson</h2><div className="field"><label htmlFor="coding-language">Execution language</label><select id="coding-language" value={language} onChange={event => setLanguage(event.target.value)}><option value="71">Python 3</option><option value="63">JavaScript</option><option value="54">C++</option><option value="62">Java</option><option value="50">C</option><option value="60">Go</option><option value="73">Rust</option></select></div><div className="field"><label htmlFor="lesson-code">Source code</label><textarea id="lesson-code" rows={14} spellCheck={false} value={code} onChange={event => setCode(event.target.value)} style={{fontFamily:'monospace'}} maxLength={100000}/></div><button className="btn btn-primary" disabled={saving || !code.trim()} onClick={runCode}>{saving ? 'Running…' : 'Run and check solution'}</button><p className="muted">An isolated execution service must be configured. A server error never counts as a passed solution.</p>{runnerResult && <pre className="code-output" style={{whiteSpace:'pre-wrap',overflowWrap:'anywhere'}}>{runnerResult}</pre>}</section> : <div className="lesson-actions"><button className="btn btn-soft" disabled={index <= 0} onClick={() => setSelectedId(lessons[index-1].id)}>← Previous</button><button className="btn btn-primary" disabled={saving} onClick={complete}>{saving ? 'Saving…' : 'Mark complete & continue →'}</button></div>}
      <p className="muted">Reading and video completion is self-reported. Coding completion is awarded by the server after a passing execution.</p>
    </> : <LearnerEmpty>No lessons are available yet.</LearnerEmpty>}
    {notice && <p role="status" className="form-error">{notice}</p>}
    {quizzes.map(quiz => <section className="panel quiz-panel" style={{padding:24,marginTop:28}} key={quiz.id}><h2>{quiz.title}</h2><p className="muted">Pass mark: {quiz.pass_percentage}%. Answers are graded by the server.</p>{quiz.questions?.map(question => <fieldset key={question.id} style={{border:'1px solid #eadfe3',padding:16,margin:'16px 0',borderRadius:12}}><legend>{question.question}</legend>{(['a','b','c','d'] as const).map(option => {const text = question[`option_${option}`];return text ? <label key={option} style={{display:'block',margin:'10px 0'}}><input type="radio" name={`quiz-${quiz.id}-question-${question.id}`} value={option} checked={answers[quiz.id]?.[String(question.id)] === option} onChange={() => setAnswers(old => ({...old,[quiz.id]:{...old[quiz.id],[String(question.id)]:option}}))}/> {text}</label> : null;})}</fieldset>)}<button className="btn btn-primary" disabled={saving || !quiz.questions?.length || quiz.questions.some(question => !answers[quiz.id]?.[String(question.id)])} onClick={() => submitQuiz(quiz)}>Submit quiz</button>{results[quiz.id] && <p role="status">{results[quiz.id].passed ? 'Passed' : 'Not yet passed'}: {results[quiz.id].score} / {results[quiz.id].total} ({Number(results[quiz.id].percentage).toFixed(1)}%)</p>}</section>)}
    </article></div>
  </main>;
}
