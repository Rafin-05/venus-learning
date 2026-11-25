'use client';

import {FormEvent, useCallback, useEffect, useState} from 'react';
import Link from 'next/link';
import PortalShell from '../../components/PortalShell';
import {all, api, patch, post, type User} from '../../lib/api';
import {LearnerEmpty, LearnerLoading} from '../../components/LearnerStates';

type MentorProfile = {id: number; user: number; mentor_name: string; mentor_email: string; qualifications: string; topics: string; hourly_rate: string; is_available: boolean};
type Wallet = {id: number; balance: string};
type Transaction = {id: number; kind: string; kind_label: string; status: string; status_label: string; amount: string; fee_amount: string; deduction_amount: string; credited_amount: string; session: number | null; note: string; created_at: string};
type Offer = {id: number; session_request: number; mentor: number; mentor_name: string; hourly_rate: string; proposed_time: string; message: string; status: string};
type SessionRequest = {id: number; student: number; student_name: string; topic: string; problem: string; tried: string; preferred_duration_hours: number; preferred_times: string[]; status: string; offers: Offer[]; created_at: string};
type Booking = {id: number; student: number; student_name: string; mentor: number; mentor_name: string; topic: string; duration_hours: number; hourly_rate: string; total_fee: string; scheduled_at: string; meet_link: string; status: string; payment_status: string; rating: {rating: number; comment: string} | null};

const money = (value: string | number) => `Tk ${Number(value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
const localTime = (value: string) => new Date(value).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'});
const toIso = (value: string) => new Date(value).toISOString();

export default function MentorHiring() {
  const [user, setUser] = useState<User | null>(null);
  const [tab, setTab] = useState<'browse' | 'requests' | 'sessions' | 'wallet'>('browse');
  const [mentors, setMentors] = useState<MentorProfile[]>([]);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [requests, setRequests] = useState<SessionRequest[]>([]);
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [myProfile, setMyProfile] = useState<MentorProfile | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [bookingForms, setBookingForms] = useState<Record<number, {topic: string; duration: string; when: string}>>({});
  const [requestForm, setRequestForm] = useState({topic: '', problem: '', tried: '', duration: '1', times: ''});
  const [offerForms, setOfferForms] = useState<Record<number, {when: string; rate: string; message: string}>>({});
  const [profileForm, setProfileForm] = useState({qualifications: '', topics: '', rate: ''});
  const [topUp, setTopUp] = useState('');
  const [meetLinks, setMeetLinks] = useState<Record<number, string>>({});
  const [ratingForms, setRatingForms] = useState<Record<number, {rating: string; comment: string}>>({});

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const me = await api<User>('/auth/me/');
      setUser(me);
      const [profiles, myWallet, entries, reqs, sessions] = await Promise.all([
        all<MentorProfile>('/mentor-hiring/mentors/'),
        api<Wallet>('/mentor-hiring/wallet/'),
        all<Transaction>('/mentor-hiring/wallet/transactions/'),
        all<SessionRequest>('/mentor-hiring/requests/'),
        all<Booking>('/mentor-hiring/bookings/'),
      ]);
      setMentors(profiles.filter(item => item.is_available));
      setMyProfile(profiles.find(item => item.user === me.id) || null);
      setWallet(myWallet); setTransactions(entries); setRequests(reqs); setBookings(sessions);
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
    const form = offerForms[request.id] || {when: '', rate: '', message: ''};
    if (!form.when) { setError('Pick a time for your offer.'); return; }
    const body: Record<string, unknown> = {session_request: request.id, proposed_time: toIso(form.when), message: form.message};
    if (form.rate) body.hourly_rate = form.rate;
    await run(() => post('/mentor-hiring/offers/', body), 'Offer sent to the learner.');
  }

  async function createProfile(event: FormEvent) {
    event.preventDefault();
    await run(() => post('/mentor-hiring/mentors/', {qualifications: profileForm.qualifications, topics: profileForm.topics, hourly_rate: profileForm.rate, is_available: true}), 'Your mentor profile is live in Browse Mentors.');
  }

  async function doTopUp(event: FormEvent) {
    event.preventDefault();
    await run(() => post('/mentor-hiring/wallet/top-up/', {amount: topUp}), 'Balance topped up.');
    setTopUp('');
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
        <button type="button" className={tab === 'wallet' ? 'active' : ''} onClick={() => setTab('wallet')}>Wallet{wallet ? ` · ${money(wallet.balance)}` : ''}</button>
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
              <p><b>Total: {money(bookingTotal(mentor))}</b> <span className="muted">({money(mentor.hourly_rate)} × {form.duration}h — paid from your wallet only after the session)</span></p>
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
            {request.offers?.length > 0 && <div>{request.offers.map(offer => <div className="activity-row" key={offer.id}><i>✦</i><span><b>{offer.mentor_name}</b> — {money(offer.hourly_rate)} / hour · {localTime(offer.proposed_time)} · total {money(Number(offer.hourly_rate) * request.preferred_duration_hours)}<small>{offer.message || 'No message'} · {offer.status}</small></span>
              {user?.role === 'learner' && request.status === 'open' && offer.status === 'pending' && <button className="btn btn-soft" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/offers/${offer.id}/accept/`, {}), 'Offer accepted — your session is booked. See My sessions.')}>Accept offer</button>}
            </div>)}</div>}
            {isMentor && request.status === 'open' && request.student !== user?.id && (() => { const form = offerForms[request.id] || {when: '', rate: myProfile ? String(myProfile.hourly_rate) : '', message: ''}; return <form onSubmit={event => makeOffer(event, request)}>
              <div className="form-grid">
                <div className="field"><label>Proposed time (your local time)</label><input type="datetime-local" required value={form.when} onChange={e => setOfferForms({...offerForms, [request.id]: {...form, when: e.target.value}})}/></div>
                <div className="field"><label>Hourly rate (Tk)</label><input type="number" min="1" step="0.01" value={form.rate} onChange={e => setOfferForms({...offerForms, [request.id]: {...form, rate: e.target.value}})}/></div>
              </div>
              <div className="field"><label>Message</label><input value={form.message} onChange={e => setOfferForms({...offerForms, [request.id]: {...form, message: e.target.value}})}/></div>
              <button className="btn btn-soft" disabled={busy}>Offer to teach</button>
            </form>; })()}
          </section>)}
          {!requests.length && <LearnerEmpty>No session requests to show.</LearnerEmpty>}
        </div>
      </>}

      {tab === 'sessions' && <div className="learning-list">
        {bookings.map(session => { const mine = session.student === user?.id; const rating = ratingForms[session.id] || {rating: '5', comment: ''}; return <section className="panel" key={session.id}>
          <div className="panel-head"><h2>{session.topic}</h2><span className="tag">{session.status} · {session.payment_status}</span></div>
          <p className="muted">{mine ? `Mentor: ${session.mentor_name}` : `Learner: ${session.student_name}`} · {localTime(session.scheduled_at)} (your local time) · {session.duration_hours}h · Total {money(session.total_fee)} ({money(session.hourly_rate)} / hour)</p>
          {session.meet_link ? <p><a className="btn btn-primary" href={session.meet_link} target="_blank" rel="noreferrer">Join Google Meet</a></p> : <p className="muted">The meeting link will appear here once the mentor adds it.</p>}
          <div className="actions">
            {!mine && session.status === 'pending' && <button className="btn btn-primary" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/confirm/`, {}), 'Booking confirmed.')}>Confirm booking</button>}
            {session.status === 'confirmed' && <button className="btn btn-soft" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/complete/`, {}), 'Session marked completed.')}>Mark completed</button>}
            {(session.status === 'pending' || session.status === 'confirmed') && <button className="btn btn-ghost" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/cancel/`, {}), 'Session cancelled. No fee is charged.')}>Cancel</button>}
            {mine && session.status === 'completed' && session.payment_status === 'unpaid' && <button className="btn btn-primary" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/pay/`, {}), 'Paid. 90% was credited to your mentor; the 10% platform deduction is in your wallet history.')}>Pay {money(session.total_fee)} from wallet</button>}
            {mine && session.payment_status === 'paid' && <button className="btn btn-ghost" disabled={busy} onClick={() => run(() => post(`/mentor-hiring/bookings/${session.id}/refund/`, {}), 'Payment refunded to your wallet balance.')}>Refund payment</button>}
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

      {tab === 'wallet' && <>
        <div className="statgrid">
          <div className="stat"><span>Current balance</span><b>{wallet ? money(wallet.balance) : '—'}</b><small>Internal wallet — session fees are paid from here, after the session</small></div>
        </div>
        <section className="panel form-panel" style={{marginTop: 20}}><div className="panel-head"><h2>Top up</h2></div>
          <form onSubmit={doTopUp}><div className="field"><label htmlFor="topup">Amount (Tk)</label><input id="topup" type="number" min="1" step="0.01" required value={topUp} onChange={e => setTopUp(e.target.value)}/></div><button className="btn btn-primary" disabled={busy}>Add balance</button></form>
        </section>
        <section className="panel" style={{marginTop: 20}}><div className="panel-head"><h2>Transaction history</h2></div>
          <div className="table-wrap"><table className="table"><thead><tr><th>Date</th><th>Type</th><th>Amount</th><th>Full fee</th><th>10% deduction</th><th>Credited</th><th>Status</th></tr></thead>
          <tbody>{transactions.map(entry => <tr key={entry.id}><td>{localTime(entry.created_at)}</td><td>{entry.kind_label}</td><td>{money(entry.amount)}</td><td>{money(entry.fee_amount)}</td><td>{money(entry.deduction_amount)}</td><td>{money(entry.credited_amount)}</td><td>{entry.status_label}</td></tr>)}</tbody></table></div>
          {!transactions.length && <LearnerEmpty>No transactions yet.</LearnerEmpty>}
        </section>
      </>}
    </>}
  </PortalShell>;
}
