'use client';
import {FormEvent, useEffect, useState} from 'react';
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import PortalShell from '../../components/PortalShell';
import AssetUpload from '../../components/AssetUpload';
import {api, patch, post, type InstructorProfile, type ProfileSummary, type User} from '../../lib/api';
import {LearnerError, LearnerLoading, LearnerEmpty} from '../../components/LearnerStates';

function localTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export default function Profile() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [summary, setSummary] = useState<ProfileSummary | null>(null);
  const [form, setForm] = useState({full_name: '', title: '', bio: '', expertise: ''});
  const [password, setPassword] = useState({current_password: '', new_password: ''});
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api<User>('/profile/'), api<ProfileSummary>('/profile/summary/')])
      .then(([me, data]) => {
        setUser(me);
        setSummary(data);
        setForm({full_name: me.full_name, title: me.title || '', bio: me.bio || '', expertise: me.expertise || ''});
      })
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load your profile.'))
      .finally(() => setLoading(false));
  }, []);

  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError(''); setMessage('');
    try {
      const updated = await patch<User>('/profile/', form);
      setUser(updated);
      setMessage('Profile updated.');
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not save profile.'); }
    finally { setBusy(false); }
  }

  async function change(event: FormEvent) {
    event.preventDefault();
    setBusy(true); setError('');
    try { await post('/auth/change-password/', password); router.push('/login?password=changed'); router.refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : 'Could not change password.'); }
    finally { setBusy(false); }
  }

  const isInstructor = user?.role === 'instructor';
  const isLearner = user?.role === 'learner';
  const isAdmin = user?.role === 'admin';
  const enrollments = summary?.enrollments || [];
  const certificates = summary?.certificates || [];
  const courses = summary?.courses || [];
  const upcoming = summary?.upcoming_sessions || [];

  return <PortalShell title="Your profile" eyebrow={user ? user.role : undefined}>
    {loading ? <LearnerLoading label="Loading your profile…" /> : error && !user ? <LearnerError message={error} retry={() => window.location.reload()} /> : user && <>
      <section className="panel form-panel">
        <div className="profile-head">
          <div className="avatar large">{user.profile_pic ? <img src={user.profile_pic} alt="Your profile" style={{width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%'}} /> : form.full_name.slice(0, 2).toUpperCase()}</div>
          <div>
            <h2>{user.full_name}</h2>
            {user.title && <p><b>{user.title}</b></p>}
            <p className="muted">{user.email} · {user.role}</p>
            {user.bio && <p>{user.bio}</p>}
            {user.expertise && <p className="muted">Expertise: {user.expertise}</p>}
          </div>
        </div>
        <AssetUpload purpose="avatar" onUploaded={url => setUser({...user, profile_pic: url})} />
        <p className="muted">Upload a square photo. It is shown on your profile, your courses and, for instructors, your public instructor page.</p>
      </section>

      <div className="statgrid">
        {isLearner && <>
          <div className="stat"><span>Enrolled courses</span><b>{enrollments.length}</b><small>Across your learning</small></div>
          <div className="stat"><span>Certificates</span><b>{certificates.length}</b><small>Issued on completion</small></div>
          <div className="stat"><span>Points</span><b>{user.points ?? 0}</b><small>From quizzes and contests</small></div>
          <div className="stat"><span>Current streak</span><b>{user.current_streak} day{user.current_streak === 1 ? '' : 's'}</b><small>Keep learning to build it</small></div>
        </>}
        {isInstructor && <>
          <div className="stat"><span>Courses taught</span><b>{courses.length}</b><small>All statuses</small></div>
          <div className="stat"><span>Students</span><b>{summary?.students ?? 0}</b><small>Across your courses</small></div>
          <div className="stat"><span>Average rating</span><b>{summary?.average_rating ? Number(summary.average_rating).toFixed(1) : '—'}</b><small>{summary?.reviews ?? 0} review{(summary?.reviews ?? 0) === 1 ? '' : 's'}</small></div>
          <div className="stat"><span>Mentor sessions done</span><b>{summary?.sessions_completed ?? 0}</b><small>Completed sessions</small></div>
        </>}
        {isAdmin && <>
          <div className="stat"><span>Users</span><b>{summary?.users ?? 0}</b><small>Registered accounts</small></div>
          <div className="stat"><span>Courses</span><b>{summary?.courses?.length ?? 0}</b><small>All statuses</small></div>
          <div className="stat"><span>Pending review</span><b>{summary?.pending_courses ?? 0}</b><small>Courses awaiting approval</small></div>
          <div className="stat"><span>Open issues</span><b>{summary?.issues ?? 0}</b><small>Support tickets</small></div>
        </>}
      </div>

      {isLearner && <div className="dashboard-columns">
        <div className="panel">
          <div className="panel-head"><h2>Continue learning</h2><Link href="/my-learning">View all</Link></div>
          {enrollments.filter(x => x.progress_percent < 100).slice(0, 4).map(item => <div className="progress-course" key={item.id}>
            <div className="mini-cover" style={{backgroundImage: `url(${item.course.thumbnail || '/course-1.png'})`}} />
            <div className="progress-info"><b>{item.course.title}</b><span>{item.progress_percent}% complete</span>
              <div className="progress"><i style={{width: `${item.progress_percent}%`}} /></div>
              <Link href={`/learning/${item.course.id}`} className="text-link">Continue learning →</Link>
            </div>
          </div>)}
          {!enrollments.some(x => x.progress_percent < 100) && <LearnerEmpty>{enrollments.length ? 'All your courses are complete.' : 'You have not enrolled in a course yet.'} <Link href="/courses" className="text-link">Explore courses →</Link></LearnerEmpty>}
        </div>
        <div className="panel">
          <div className="panel-head"><h2>Certificates</h2><Link href="/certificates">View all</Link></div>
          {certificates.slice(0, 4).map(cert => <div className="activity-row" key={cert.id}><i>✓</i><span><b>{cert.course.title}</b><small>Issued {localTime(cert.issued_at)} · {cert.certificate_no}</small></span></div>)}
          {!certificates.length && <LearnerEmpty>No certificates yet. Finish a course to earn one.</LearnerEmpty>}
          <div className="panel-head"><h2>Upcoming mentor sessions</h2><Link href="/mentor-hiring">Mentor hiring</Link></div>
          {upcoming.slice(0, 4).map(session => <div className="activity-row" key={session.id}><i>✦</i><span><b>{session.topic}</b> with {session.mentor_name}<small>{localTime(session.scheduled_at)} · {session.duration_hours}h · {session.status}</small></span></div>)}
          {!upcoming.length && <p className="muted">No mentor sessions booked. <Link href="/mentor-hiring" className="text-link">Browse mentors →</Link></p>}
        </div>
      </div>}

      {isInstructor && <div className="dashboard-columns">
        <div className="panel">
          <div className="panel-head"><h2>Courses you teach</h2><Link href="/instructor/courses">Manage courses</Link></div>
          {courses.slice(0, 5).map(course => <div className="activity-row" key={course.id}><i>▸</i><span><b>{course.title}</b><small>{course.status} · {course.student_count ?? 0} students · {course.average_rating ? `${Number(course.average_rating).toFixed(1)} / 5` : 'No ratings yet'} · {course.lesson_count ?? 0} lessons</small></span></div>)}
          {!courses.length && <LearnerEmpty>You have not created a course yet. <Link href="/instructor/courses/new" className="text-link">Create one →</Link></LearnerEmpty>}
          <p><Link href={`/instructors/${user.id}`} className="text-link">View your public instructor page →</Link></p>
        </div>
        <div className="panel">
          <div className="panel-head"><h2>Mentor overview</h2><Link href="/mentor-hiring">Mentor hiring</Link></div>
          {summary?.mentor_profile ? <>
            <p><b>{summary.mentor_profile.hourly_rate} Tk</b> per hour · {summary.mentor_profile.is_available ? 'Available' : 'Not available'}</p>
            <p className="muted">{summary.mentor_profile.topics}</p>
            <p><b>Qualifications</b></p>
            <p>{summary.mentor_profile.qualifications || 'Not listed yet.'}</p>
          </> : <p className="muted">You have no mentor profile yet. <Link href="/mentor-hiring" className="text-link">Create one in Mentor hiring →</Link></p>}
          <div className="panel-head"><h2>Upcoming mentor sessions</h2></div>
          {upcoming.slice(0, 4).map(session => <div className="activity-row" key={session.id}><i>✦</i><span><b>{session.topic}</b> with {session.student_name}<small>{localTime(session.scheduled_at)} · {session.duration_hours}h · {session.status}</small></span></div>)}
          {!upcoming.length && <p className="muted">No upcoming mentor sessions.</p>}
        </div>
      </div>}

      <section className="panel form-panel">
        <div className="panel-head"><h2>Edit profile</h2></div>
        {error && <p className="form-error" role="alert">{error}</p>}
        <form onSubmit={save}>
          <div className="field"><label htmlFor="full_name">Full name</label><input id="full_name" required maxLength={150} value={form.full_name} onChange={e => setForm({...form, full_name: e.target.value})} /></div>
          {!isLearner && <div className="field"><label htmlFor="title">Professional title</label><input id="title" maxLength={150} value={form.title} onChange={e => setForm({...form, title: e.target.value})} placeholder="e.g. Senior Data Science Instructor" /></div>}
          <div className="field"><label htmlFor="expertise">Areas of interest</label><input id="expertise" maxLength={200} value={form.expertise} onChange={e => setForm({...form, expertise: e.target.value})} /></div>
          <div className="field"><label htmlFor="bio">About you</label><textarea id="bio" rows={5} maxLength={2000} value={form.bio} onChange={e => setForm({...form, bio: e.target.value})} /></div>
          <button className="btn btn-primary" disabled={busy}>Save changes</button>
          {message && <p className="success" role="status">{message}</p>}
        </form>
      </section>

      <form className="panel form-panel" onSubmit={change}>
        <h2>Change password</h2>
        <p className="muted">This signs out all sessions. Sign in again with the new password.</p>
        <div className="field"><label htmlFor="current-password">Current password</label><input id="current-password" type="password" autoComplete="current-password" required value={password.current_password} onChange={e => setPassword({...password, current_password: e.target.value})} /></div>
        <div className="field"><label htmlFor="new-password">New password</label><input id="new-password" type="password" autoComplete="new-password" required minLength={10} maxLength={128} value={password.new_password} onChange={e => setPassword({...password, new_password: e.target.value})} /></div>
        <button className="btn btn-primary" disabled={busy}>Change password</button>
      </form>
    </>}
  </PortalShell>;
}
