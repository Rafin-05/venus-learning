'use client';

import {FormEvent, useCallback, useEffect, useState} from 'react';
import Link from 'next/link';
import PortalShell from '../../components/PortalShell';
import {all, api, patch, post, type User} from '../../lib/api';
import {LearnerEmpty, LearnerLoading} from '../../components/LearnerStates';

type MentorProfile = {id: number; user: number; mentor_name: string; mentor_email: string; qualifications: string; topics: string; hourly_rate: string; is_available: boolean};
type Offer = {id: number; session_request: number; mentor: number; mentor_name: string; hourly_rate: string; pricing_type: string; agreed_amount: string | null; proposed_time: string; message: string; status: string};
type SessionRequest = {id: number; student: number; student_name: string; topic: string; problem: string; tried: string; preferred_duration_hours: number; preferred_times: string[]; status: string; offers: Offer[]; created_at: string};
type Booking = {id: number; student: number; student_name: string; mentor: number; mentor_name: string; topic: string; duration_hours: number; hourly_rate: string; pricing_type: string; agreed_amount: string | null; total_fee: string; scheduled_at: string; started_at: string | null; ended_at: string | null; elapsed_minutes: number | null; meet_link: string; status: string; payment_status: string; rating: {rating: number; comment: string} | null};

const money = (value: string | number) => `Tk ${Number(value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
const localTime = (value: string) => new Date(value).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'});
const toIso = (value: string) => new Date(value).toISOString();

export default function MentorHiring() {
  const [user, setUser] = useState<User | null>(null);
  const [tab, setTab] = useState<'browse' | 'requests' | 'sessions'>('browse');
  const [mentors, setMentors] = useState<MentorProfile[]>([]);
  const [requests, setRequests] = useState<SessionRequest[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [myProfile, setMyProfile] = useState<MentorProfile | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [bookingForms, setBookingForms] = useState<Record<number, {topic: string; duration: string; when: string}>>({});
  const [requestForm, setRequestForm] = useState({topic: '', problem: '', tried: '', duration: '1', times: ''});
  const [offerForms, setOfferForms] = useState<Record<number, {when: string; rate: string; message: string; pricing: 'hourly' | 'fixed'; amount: string}>>({});
  const [profileForm, setProfileForm] = useState({qualifications: '', topics: '', rate: ''});
  const [meetLinks, setMeetLinks] = useState<Record<number, string>>({});
  const [ratingForms, setRatingForms] = useState<Record<number, {rating: string; comment: string}>>({});
  const [joined, setJoined] = useState<Record<number, boolean>>({});
  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => { const timer = window.setInterval(() => setNowMs(Date.now()), 1000); return () => window.clearInterval(timer); }, []);
  useEffect(() => {
    if (tab !== 'sessions') return;
    const timer = window.setInterval(async () => {
      try { setBookings(await all<Booking>('/mentor-hiring/bookings/')); } catch { /* Keep the last loaded sessions; the next refresh retries. */ }
    }, 10000);
    return () => window.clearInterval(timer);
  }, [tab]);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const me = await api<User>('/auth/me/');
      setUser(me);
      const [profiles, reqs, sessions] = await Promise.all([
        all<MentorProfile>('/mentor-hiring/mentors/'),
        all<SessionRequest>('/mentor-hiring/requests/'),
        all<Booking>('/mentor-hiring/bookings/'),
      ]);
      setMentors(profiles.filter(item => item.is_available));
      setMyProfile(profiles.find(item => item.user === me.id) || null);
      setRequests(reqs); setBookings(sessions);
    } catch (err) { setError(err instanceof Error ? err.message : 'Could not load mentor hiring.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setError(''); setNotice('');
    try { await action(); setNotice(success); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : 'The request could not be completed.'); }
    finally { setBusy(false); }
  }

  const elapsedText = (startedAt: string | null, endedAt: string | null) => {
    if (!startedAt) return '';
    const end = endedAt ? new Date(endedAt).getTime() : nowMs;
    const seconds = Math.max(0, Math.floor((end - new Date(startedAt).getTime()) / 1000));
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return hours > 0 ? `${hours}h ${minutes}m ${secs}s` : `${minutes}m ${secs}s`;
  };

  async function endSession(session: Booking) {
    setBusy(true); setError(''); setNotice('');
    try {
      const result = await post<{elapsed_minutes: number; total_fee: string; platform_deduction: string; credited_to_mentor: string}>(`/mentor-hiring/bookings/${session.id}/end/`, {});
      setNotice(`Session ended after ${result.elapsed_minutes} min. Final fare ${money(result.total_fee)} — the mentor receives ${money(result.credited_to_mentor)} after the 10% platform deduction (${money(result.platform_deduction)}).`);
      await load();
    } catch (err) { setError(err instanceof Error ? err.message : 'The session could not be ended.'); }
    finally { setBusy(false); }
  }

  async function book(event: FormEvent, mentor: MentorProfile) {
    event.preventDefault();
    const form = bookingForms[mentor.id] || {topic: '', duration: '1', when: ''};
    if (!form.topic || !form.when) { setError('Add a topic and pick a time slot before booking.'); return; }
    await run(() => post('/mentor-hiring/bookings/', {mentor: mentor.user, topic: form.topic, duration_hours: Number(form.duration), scheduled_at: toIso(form.when)}), 'Booking request sent. The mentor confirms it before the session is final.');
  }

  async function createRequest(event: FormEvent) {
    event.preventDefault();
    await run(() => post('/mentor-hiring/requests/', {topic: requestForm.topic, problem: requestForm.problem, tried: requestForm.tried, preferred_duration_hours: Number(requestForm.duration), preferred_times: requestForm.times ? requestForm.times.split(',').map(item => item.trim()).filter(Boolean) : []}), 'Your session request is on the board. Mentors can now make offers.');
    setRequestForm({topic: '', problem: '', tried: '', duration: '1', times: ''});
  }

  async function makeOffer(event: FormEvent, request: SessionRequest) {
    event.preventDefault();
    const form = offerForms[request.id] || {when: '', rate: '', message: '', pricing: 'hourly', amount: ''};
    if (!form.when) { setError('Pick a time for your offer.'); return; }
    const body: Record<string, unknown> = {session_request: request.id, proposed_time: toIso(form.when), message: form.message, pricing_type: form.pricing};
    if (form.rate) body.hourly_rate = form.rate;
    if (form.pricing === 'fixed') {
      if (!form.amount || Number(form.amount) <= 0) { setError('A fixed-price offer needs an agreed amount above zero.'); return; }
      body.agreed_amount = form.amount;
    }
    await run(() => post('/mentor-hiring/offers/', body), 'Offer sent to the learner.');
  }

  async function createProfile(event: FormEvent) {
    event.preventDefault();
    await run(() => post('/mentor-hiring/mentors/', {qualifications: profileForm.qualifications, topics: profileForm.topics, hourly_rate: profileForm.rate, is_available: true}), 'Your mentor profile is live in Browse Mentors.');
  }

  const isMentor = user?.role === 'instructor';
  const bookingTotal = (mentor: MentorProfile) => Number(mentor.hourly_rate) * Number((bookingForms[mentor.id]?.duration) || '1');

  return <PortalShell title="Mentor hiring" eyebrow="1-to-1 sessions">
    {loading ? <LearnerLoading label="Loading mentor hiring…"/> : <>
      {error && <p className="form-error" role="alert">{error}</p>}
      {notice && <p className="success" role="status">{notice}</p>}
      <div className="tabs" role="tablist">
        <button type="button" className={tab === 'browse' ? 'active' : ''} onClick={() => setTab('browse')}>Browse mentors</button>
        <button type="button" className={tab === 'requests' ? 'active' : ''} onClick={() => setTab('requests')}>Session requests</button>
        <button type="button" className={tab === 'sessions' ? 'active' : ''} onClick={() => setTab('sessions')}>My sessions</button>
      </div>

      {tab === 'browse' && <>
        {isMentor && !myProfile && <section className="panel form-panel"><div className="panel-head"><h2>Create your mentor profile</h2></div>
          <form onSubmit={createProfile}>
            <div className="field"><label htmlFor="qualifications">Qualifications</label><textarea id="qualifications" rows={3} required value={profileForm.qualifications} onChange={e => setProfileForm({...profileForm, qualifications: e.target.value})}/></div>
            <div className="field"><label htmlFor="topics">Expertise / topics</label><input id="topics" required maxLength={500} value={profileForm.topics} onChange={e => setProfileForm({...profileForm, topics: e.target.value})}/></div>
            <div className="field"><label htmlFor="rate">Hourly rate (Tk)</label><input id="rate" type="number" min="1" step="0.01" required value={profileForm.rate} onChange={e => setProfileForm({...profileForm, rate: e.target.value})}/></div>
            <button className="btn btn-primary" disabled={busy}>Publish profile</button>
          </form></section>}
        {isMentor && myProfile && <section className="panel"><div className="panel-head"><h2>Your mentor profile</h2></div><p><b>{money(myProfile.hourly_rate)}</b> per hour · {myProfile.topics}</p><p className="muted">{myProfile.qualifications}</p></section>}
        <div className="cards">
          {mentors.filter(mentor => mentor.user !== user?.id).map(mentor => { const form = bookingForms[mentor.id] || {topic: '', duration: '1', when: ''}; return <article className="course-card" key={mentor.id}><div className="course-body">
            <span className="tag">{money(mentor.hourly_rate)} / hour</span>
            <h3>{mentor.mentor_name}</h3>
            <p><Link href={`/instructors/${mentor.user}`} className="text-link">View full profile →</Link></p>
            <p className="muted">{mentor.qualifications}</p>
            <p><b>Expertise:</b> {mentor.topics}</p>
            {user?.role === 'learner' && <form onSubmit={event => book(event, mentor)}>
              <div className="field"><label>Topic you need help with</label><input required value={form.topic} onChange={e => setBookingForms({...bookingForms, [mentor.id]: {...form, topic: e.target.value}})}/></div>
              <div className="field"><label>Duration</label><select value={form.duration} onChange={e => setBookingForms({...bookingForms, [mentor.id]: {...form, duration: e.target.value}})}><option value="1">1 hour</option><option value="2">2 hours</option></select></div>
              <div className="field"><label>Time slot (your local time)</label><input type="datetime-local" required value={form.when} onChange={e => setBookingForms({...bookingForms, [mentor.id]: {...form, when: e.target.value}})}/></div>
              <p><b>Total: {money(bookingTotal(mentor))}</b> <span className="muted">({money(mentor.hourly_rate)} × {form.duration}h — paid from your Finance balance only after the session)</span></p>
              <button className="btn btn-primary" disabled={busy}>Send booking request</button>
            </form>}
          </div></article>; })}
        </div>
        {!mentors.length && <LearnerEmpty>No mentors are available yet.</LearnerEmpty>}
      </>}

      {tab === 'requests' && <>
        {user?.role === 'learner' && <section className="panel form-panel"><div className="panel-head"><h2>Post what you are stuck on</h2></div>
          <form onSubmit={createRequest}>
            <div className="field"><label htmlFor="req-topic">Topic</label><input id="req-topic" required maxLength={200} value={requestForm.topic} onChange={e => setRequestForm({...requestForm, topic: e.target.value})} placeholder="e.g. Backtracking"/></div>
            <div className="field"><label htmlFor="req-problem">What are you stuck on?</label><textarea id="req-problem" rows={3} required value={requestForm.problem} onChange={e => setRequestForm({...requestForm, problem: e.target.value})}/></div>
            <div className="field"><label htmlFor="req-tried">What have you tried?</label><textarea id="req-tried" rows={2} value={requestForm.tried} onChange={e => setRequestForm({...requestForm, tried: e.target.value})}/></div>
            <div className="form-grid">
              <div className="field"><label htmlFor="req-duration">Preferred duration</label><select id="req-duration" value={requestForm.duration} onChange={e => setRequestForm({...requestForm, duration: e.target.value})}><option value="1">1 hour</option><option value="2">2 hours</option></select></div>
              <div className="field"><label htmlFor="req-times">Preferred times (comma separated)</label><input id="req-times" value={requestForm.times} onChange={e => setRequestForm({...requestForm, times: e.target.value})} placeholder="Saturday 10:00, Sunday 18:00"/></div>
            </div>
            <button className="btn btn-primary" disabled={busy}>Post request</button>
          </form></section>}
        <div className="learning-list" style={{marginTop: 20}}>
          {requests.map(request => <section className="panel" key={request.id}>
            <div className="panel-head"><h2>{request.topic}</h2><span className="tag">{request.status}</span></div>
            <p>{request.problem}</p>
            {request.tried && <p className="muted"><b>Tried:</b> {request.tried}</p>}
            <p className="muted">By {request.student_name} · {request.preferred_duration_hours} hour{request.preferred_duration_hours === 1 ? '' : 's'}{request.preferred_times?.length ? ` · Prefers: ${request.preferred_times.join(', ')}` : ''}</p>
            {request.offers?.length > 0 && <div>{request.offers.map(offer => <div className="activity-row" key={offer.id}><i>✦</i><span><b>{offer.mentor_name}</b> — {offer.pricing_type === 'fixed' ? `Fixed ${money(offer.agreed_amount || 0)} total` : `${money(offer.hourly_rate)} / hour · total ${money(Number(offer.hourly_rate) * request.preferred_duration_hours)}`} · {localTime(offer.proposed_time)}<small>{offer.message || 'No message'} · {offer.status}</small></span>
              {user?.role === 'learner' && request.status === 'open' && offer.status === 'pending' && <button className="btn btn-soft" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/offers/${offer.id}/accept/`, {}), 'Offer accepted — your session is booked. See My sessions.')}>Accept offer</button>}
            </div>)}</div>}
            {isMentor && request.status === 'open' && request.student !== user?.id && (() => { const form = offerForms[request.id] || {when: '', rate: myProfile ? String(myProfile.hourly_rate) : '', message: '', pricing: 'hourly', amount: ''}; return <form onSubmit={event => makeOffer(event, request)}>
              <div className="form-grid">
                <div className="field"><label>Proposed time (your local time)</label><input type="datetime-local" required value={form.when} onChange={e => setOfferForms({...offerForms, [request.id]: {...form, when: e.target.value}})}/></div>
                <div className="field"><label>Hourly rate (Tk)</label><input type="number" min="1" step="0.01" value={form.rate} onChange={e => setOfferForms({...offerForms, [request.id]: {...form, rate: e.target.value}})}/></div>
              </div>
              <div className="form-grid">
                <div className="field"><label>Pricing</label><select value={form.pricing} onChange={e => setOfferForms({...offerForms, [request.id]: {...form, pricing: e.target.value as 'hourly' | 'fixed'}})}><option value="hourly">Hourly</option><option value="fixed">Fixed amount</option></select></div>
                {form.pricing === 'fixed' && <div className="field"><label>Agreed fixed amount (Tk)</label><input type="number" min="1" step="0.01" required value={form.amount} onChange={e => setOfferForms({...offerForms, [request.id]: {...form, amount: e.target.value}})}/></div>}
              </div>
              <div className="field"><label>Message</label><input value={form.message} onChange={e => setOfferForms({...offerForms, [request.id]: {...form, message: e.target.value}})}/></div>
              <button className="btn btn-soft" disabled={busy}>Offer to teach</button>
            </form>; })()}
          </section>)}
          {!requests.length && <LearnerEmpty>No session requests to show.</LearnerEmpty>}
        </div>
      </>}

      {tab === 'sessions' && <div className="learning-list">
        <p className="muted">Session fees are paid from your <Link href="/finance"><b>Finance</b></Link> balance after the session. Mentors receive 90%; the 10% platform deduction is listed in your finance history.</p>
        {bookings.map(session => { const mine = session.student === user?.id; const rating = ratingForms[session.id] || {rating: '5', comment: ''}; return <section className="panel" key={session.id}>
          <div className="panel-head"><h2>{session.topic}</h2><span className="tag">{session.status} · {session.payment_status}</span></div>
          <p className="muted">{mine ? `Mentor: ${session.mentor_name}` : `Learner: ${session.student_name}`} · {localTime(session.scheduled_at)} (your local time) · {session.duration_hours}h · Total {money(session.total_fee)} ({session.pricing_type === 'fixed' ? `Fixed ${money(session.agreed_amount || 0)}` : `${money(session.hourly_rate)} / hour`})</p>
          {mine && session.status === 'live' && (joined[session.id] ? <p role="status"><b>You are in the class</b> · {elapsedText(session.started_at, session.ended_at)}</p> : <p><a className="btn btn-primary" href={session.meet_link} target="_blank" rel="noreferrer" onClick={() => setJoined({...joined, [session.id]: true})}>Join now</a></p>)}
          {mine && session.status === 'confirmed' && <p className="muted">Join now will appear here once your mentor starts the session.</p>}
          {!mine && (session.meet_link ? <p><a className="btn btn-primary" href={session.meet_link} target="_blank" rel="noreferrer">Join Google Meet</a></p> : <p className="muted">Add the Google Meet link below — the session cannot start without it.</p>)}
          {!mine && session.status === 'live' && <p role="status"><b>Class in progress</b> · {elapsedText(session.started_at, session.ended_at)}</p>}
          {session.status === 'completed' && session.started_at && <p className="muted">Class lasted {elapsedText(session.started_at, session.ended_at)} · Final fare {money(session.total_fee)} — mentor receives {money(Number(session.total_fee) * 0.9)} after the 10% platform deduction.</p>}
          <div className="actions">
            {!mine && session.status === 'pending' && <button className="btn btn-primary" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/confirm/`, {}), 'Booking confirmed.')}>Confirm booking</button>}
            {!mine && session.status === 'confirmed' && <button className="btn btn-primary" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/start/`, {}), 'Session started — the learner can now join.')}>Start session</button>}
            {!mine && session.status === 'live' && <button className="btn btn-primary" disabled={busy} onClick={() => endSession(session)}>End session</button>}
            {session.status === 'confirmed' && <button className="btn btn-soft" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/complete/`, {}), 'Session marked completed.')}>Mark completed</button>}
            {(session.status === 'pending' || session.status === 'confirmed') && <button className="btn btn-ghost" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/cancel/`, {}), 'Session cancelled. No fee is charged.')}>Cancel</button>}
            {mine && session.status === 'completed' && session.payment_status === 'unpaid' && <button className="btn btn-primary" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/pay/`, {}), 'Paid. 90% was credited to your mentor; the 10% platform deduction is in your Finance history.')}>Pay {money(session.total_fee)} from Finance</button>}
            {mine && session.payment_status === 'paid' && <button className="btn btn-ghost" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/refund/`, {}), 'Payment refunded to your Finance balance.')}>Refund payment</button>}
          </div>
          {!mine && session.status !== 'cancelled' && <div className="field"><label>Google Meet link</label><div className="searchbar"><input type="url" placeholder="https://meet.google.com/…" value={meetLinks[session.id] ?? session.meet_link ?? ''} onChange={e => setMeetLinks({...meetLinks, [session.id]: e.target.value})}/><button className="btn btn-soft" disabled={busy} onClick={() => run(() => patch(`/mentor-hiring/bookings/${session.id}/`, {meet_link: meetLinks[session.id] || ''}), 'Meeting link saved.')}>Save link</button></div></div>}
          {mine && session.status === 'completed' && !session.rating && <form onSubmit={event => { event.preventDefault(); run(() => post('/mentor-hiring/ratings/', {session: session.id, rating: Number(rating.rating), comment: rating.comment}), 'Thanks — your rating was recorded.'); }}>
            <div className="form-grid">
              <div className="field"><label>Rate this session</label><select value={rating.rating} onChange={e => setRatingForms({...ratingForms, [session.id]: {...rating, rating: e.target.value}})}><option value="5">5 — Excellent</option><option value="4">4 — Good</option><option value="3">3 — Okay</option><option value="2">2 — Poor</option><option value="1">1 — Very poor</option></select></div>
              <div className="field"><label>Comment (optional)</label><input value={rating.comment} onChange={e => setRatingForms({...ratingForms, [session.id]: {...rating, comment: e.target.value}})}/></div>
            </div>
            <button className="btn btn-soft" disabled={busy}>Submit rating</button>
          </form>}
          {session.rating && <p className="muted">Rated {session.rating.rating} / 5{session.rating.comment ? ` — “${session.rating.comment}”` : ''}</p>}
        </section>; })}
        {!bookings.length && <LearnerEmpty>No sessions yet. Book from Browse mentors or accept an offer on the request board.</LearnerEmpty>}
      </div>}
    </>}
  </PortalShell>;
}
