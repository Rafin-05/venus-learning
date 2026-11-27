'use client';
import Link from 'next/link';
import {useParams} from 'next/navigation';
import {useEffect, useState} from 'react';
import ProctorMonitor from '../../../../components/ProctorMonitor';
import {api, post} from '../../../../lib/api';

/**
 * Proctored exam page. This is a wrapper around the existing quiz: it
 * loads the same quiz the learner would take on the course learning
 * page and submits answers to the same /quizzes/<id>/submit/ endpoint,
 * so quiz grading is completely unchanged. The only addition is the
 * ProctorMonitor above the questions, which runs only while the exam
 * is in progress. The questions stay locked until monitoring is active.
 */

type Question = {id: number; question: string; option_a: string; option_b: string; option_c?: string; option_d?: string};
type Quiz = {id: number; course: number; title: string; pass_percentage: number; questions: Question[]};
type Result = {passed: boolean; score: number; total: number; percentage: number | string};

export default function ProctoredExam() {
  const {id} = useParams<{id: string}>();
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [monitoring, setMonitoring] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const [stopped, setStopped] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api<Quiz>(`/quizzes/${id}/`)
      .then(setQuiz)
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load this exam.'))
      .finally(() => setLoading(false));
  }, [id]);

  async function submit() {
    if (!quiz || !monitoring) return;
    setSaving(true);
    setError('');
    try {
      const value = await post<Result>(`/quizzes/${quiz.id}/submit/`, {answers});
      setResult(value);
      setStopped(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not submit this exam.');
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="container section"><p className="muted" aria-live="polite">Loading exam…</p></main>;
  if (!quiz) {
    return (
      <main className="container section">
        <div className="panel"><h1>Exam not found</h1><p className="form-error">{error || 'This exam could not be loaded.'}</p><Link className="btn btn-primary" href="/my-learning">Back to My learning</Link></div>
      </main>
    );
  }

  const allAnswered = quiz.questions?.length > 0 && quiz.questions.every(q => answers[String(q.id)]);

  return (
    <main className="container section">
      <div className="page-title"><div><div className="eyebrow">Monitored exam</div><h1>{quiz.title}</h1></div></div>
      <ProctorMonitor
        quizId={quiz.id}
        stopped={stopped}
        onSessionChange={() => undefined}
        onMonitoringChange={(active, isBlocked) => { setMonitoring(active); setBlocked(isBlocked); }}
      />
      {blocked && (
        <div className="panel" role="alert">
          <h2>Answer the exam once your camera is on</h2>
          <p className="muted">The questions below unlock as soon as the camera check passes.</p>
        </div>
      )}
      {monitoring && !result && (
        <section className="panel quiz-panel" style={{padding: 24, marginTop: 28}}>
          <h2>Questions</h2>
          <p className="muted">Pass mark: {quiz.pass_percentage}%. Answers are graded by the server. Monitoring stays on until you submit.</p>
          {quiz.questions?.map(question => (
            <fieldset key={question.id} style={{border: '1px solid #eadfe3', padding: 16, margin: '16px 0', borderRadius: 12}}>
              <legend>{question.question}</legend>
              {(['a', 'b', 'c', 'd'] as const).map(option => {
                const text = question[`option_${option}`];
                return text ? (
                  <label key={option} style={{display: 'block', margin: '10px 0'}}>
                    <input type="radio" name={`proctored-${quiz.id}-question-${question.id}`} value={option} checked={answers[String(question.id)] === option} onChange={() => setAnswers(old => ({...old, [String(question.id)]: option}))} /> {text}
                  </label>
                ) : null;
              })}
            </fieldset>
          ))}
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="btn btn-primary" disabled={saving || !allAnswered} onClick={() => void submit()}>
            {saving ? 'Submitting…' : 'Submit exam'}
          </button>
        </section>
      )}
      {result && (
        <div className="panel" role="status" style={{marginTop: 28}}>
          <h2>{result.passed ? 'Passed' : 'Not yet passed'}</h2>
          <p>{result.score} / {result.total} ({Number(result.percentage).toFixed(1)}%)</p>
          <p className="muted">Monitoring has ended and the camera is off.</p>
          <Link className="btn btn-primary" href={`/learning/${quiz.course}`}>Back to the course</Link>
        </div>
      )}
    </main>
  );
}
