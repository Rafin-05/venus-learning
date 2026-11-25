'use client';
import {use, useEffect, useState} from 'react';
import Link from 'next/link';
import PortalShell from '../../../components/PortalShell';
import {api, type InstructorProfile} from '../../../lib/api';
import {LearnerError, LearnerLoading, LearnerEmpty} from '../../../components/LearnerStates';

export default function InstructorProfilePage({params}: {params: Promise<{id: string}>}) {
  const {id} = use(params);
  const [data, setData] = useState<InstructorProfile | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<InstructorProfile>(`/instructors/${id}/`)
      .then(setData)
      .catch(err => setError(err instanceof Error ? err.message : 'Could not load this instructor.'))
      .finally(() => setLoading(false));
  }, [id]);

  const instructor = data?.user;
  const courses = data?.courses || [];
  const mentor = data?.mentor_profile;

  return <PortalShell title={instructor ? `${instructor.full_name}` : 'Instructor profile'} eyebrow="Instructors">
    {loading ? <LearnerLoading label="Loading instructor profile…" /> : error || !data || !instructor ? <LearnerError message={error || 'This instructor profile is not available.'} retry={() => window.location.reload()} /> : <>
      <section className="panel form-panel">
        <div className="profile-head">
          <div className="avatar large">{instructor.profile_pic ? <img src={instructor.profile_pic} alt={instructor.full_name} style={{width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%'}} /> : instructor.full_name.slice(0, 2).toUpperCase()}</div>
          <div>
            <h2>{instructor.full_name}</h2>
            {instructor.title && <p><b>{instructor.title}</b></p>}
            {instructor.bio && <p>{instructor.bio}</p>}
            {instructor.expertise && <p className="muted">Expertise: {instructor.expertise}</p>}
          </div>
        </div>
      </section>

      <div className="statgrid">
        <div className="stat"><span>Courses taught</span><b>{courses.length}</b><small>Published courses</small></div>
        <div className="stat"><span>Students</span><b>{data.students}</b><small>Across all courses</small></div>
        <div className="stat"><span>Average rating</span><b>{data.average_rating ? Number(data.average_rating).toFixed(1) : '—'}</b><small>{data.reviews} review{data.reviews === 1 ? '' : 's'}</small></div>
        <div className="stat"><span>Mentor sessions done</span><b>{data.sessions_completed}</b><small>Completed sessions</small></div>
      </div>

      <div className="dashboard-columns">
        <div className="panel">
          <div className="panel-head"><h2>Courses taught</h2></div>
          {courses.map(course => <div className="activity-row" key={course.id}><i>▸</i><span><b>{course.title}</b><small>{course.student_count ?? 0} students · {course.average_rating ? `${Number(course.average_rating).toFixed(1)} / 5` : 'No ratings yet'} · {course.lesson_count ?? 0} lessons</small><Link href={`/courses/${course.id}`} className="text-link">View course →</Link></span></div>)}
          {!courses.length && <LearnerEmpty>This instructor has no published courses yet.</LearnerEmpty>}
        </div>
        <div className="panel">
          <div className="panel-head"><h2>Mentor sessions</h2><Link href="/mentor-hiring">Mentor hiring</Link></div>
          {mentor ? <>
            <p><b>{mentor.hourly_rate} Tk</b> per hour · {mentor.is_available ? 'Available' : 'Not available'}</p>
            <p className="muted">{mentor.topics}</p>
            <p><b>Qualifications</b></p>
            <p>{mentor.qualifications || 'Not listed yet.'}</p>
            <Link href="/mentor-hiring" className="btn btn-primary">Book a mentor session</Link>
          </> : <p className="muted">This instructor does not offer mentor sessions yet.</p>}
        </div>
      </div>
    </>}
  </PortalShell>;
}
