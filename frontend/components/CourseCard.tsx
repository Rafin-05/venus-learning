'use client';
import Link from 'next/link';
import type {Course} from '../lib/api';

function imageSource(value: string | undefined, fallback: string): string {
  if (!value) return fallback;
  if (value.startsWith('/') && !value.startsWith('//')) return value;
  try { const url = new URL(value); return url.protocol === 'https:' ? url.href : fallback; }
  catch { return fallback; }
}
export default function CourseCard({course, index = 0}: {course: Course; index?: number}) {
  const fallback = ['/course-1.png', '/course-2.png', '/hero-cover.png'][index % 3];
  return <article className="course-card">
    <div className="course-cover"><img src={imageSource(course.thumbnail, fallback)} alt="" loading="lazy" referrerPolicy="no-referrer" style={{width:'100%',height:'100%',objectFit:'cover'}} onError={event => {event.currentTarget.onerror = null; event.currentTarget.src = fallback;}}/></div>
    <div className="course-body"><span className="tag">{course.category || 'Learning path'}</span>
      <h3><Link href={`/courses/${course.id}`}>{course.title}</Link></h3>
      <p className="muted" style={{minHeight:42}}>{course.description?.slice(0,92) || 'Build practical skills with a clear, guided curriculum.'}</p>
      <div className="meta"><span>By {course.instructor_name || 'Venus instructor'}</span><span className="stars">Rating {course.average_rating ? Number(course.average_rating).toFixed(1) : '—'}</span></div>
    </div>
  </article>;
}
