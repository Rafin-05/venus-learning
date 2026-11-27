'use client';

import {FormEvent, useCallback, useEffect, useState} from 'react';
import {useRouter} from 'next/navigation';
import PortalShell from '../../components/PortalShell';
import {all, api, post} from '../../lib/api';
import {LearnerEmpty, LearnerError, LearnerLoading} from '../../components/LearnerStates';

type Method = {value: string; label: string};

type Summary = {
  balance: string; role: string; can_withdraw: boolean; payment_methods: Method[];
  pending_top_ups: number; approved_top_ups: string; pending_withdrawals: number; paid_withdrawals: string;
};

type TopUp = {
  id: number; method: string; method_label: string; account_number: string; transaction_id: string;
  amount: string; status: string; status_label: string; review_note: string; created_at: string;
};

type Withdrawal = {
  id: number; method: string; method_label: string; account_number: string; amount: string;
  status: string; status_label: string; review_note: string; created_at: string;
};

type LedgerEntry = {
  id: number; kind: string; kind_label: string; status: string; status_label: string;
  amount: string; note: string; created_at: string;
};

const money = (value: string | number) => `Tk ${Number(value).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
const localTime = (value: string) => new Date(value).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'short'});
const statusClass = (status: string) => status === 'pending' ? 't-wait' : ['approved', 'paid', 'completed'].includes(status) ? 't-ok' : 't-no';

export default function FinancePage() {
  const router = useRouter();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [topUps, setTopUps] = useState<TopUp[]>([]);
  const [withdrawals, setWithdrawals] = useState<Withdrawal[]>([]);
  const [ledger, setLedger] = useState<LedgerEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [topUpForm, setTopUpForm] = useState({method: 'bkash', amount: '', account: '', transaction: ''});
  const [withdrawForm, setWithdrawForm] = useState({method: 'bkash', amount: '', account: ''});

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const [account, topUpRows, withdrawalRows, entries] = await Promise.all([
        api<Summary>('/finance/'),
        all<TopUp>('/finance/top-ups/'),
        all<Withdrawal>('/finance/withdrawals/'),
        all<LedgerEntry>('/finance/transactions/'),
      ]);
      setSummary(account); setTopUps(topUpRows); setWithdrawals(withdrawalRows); setLedger(entries);
    } catch (err) {
      if (err instanceof Error && err.message.startsWith('401')) router.push('/login');
      else setError(err instanceof Error ? err.message : 'Could not load your finance account.');
    } finally { setLoading(false); }
  }, [router]);

  useEffect(() => { load(); }, [load]);

  async function submitTopUp(event: FormEvent) {
    event.preventDefault();
    setBusy('top-up'); setError(''); setNotice('');
    try {
      await post('/finance/top-ups/', {
        method: topUpForm.method, amount: topUpForm.amount,
        account_number: topUpForm.account, transaction_id: topUpForm.transaction,
      });
      setTopUpForm({...topUpForm, amount: '', transaction: ''});
      setNotice('Top-up submitted. Your balance updates as soon as the transaction is verified.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The top-up could not be submitted.');
    } finally { setBusy(''); }
  }

  async function submitWithdrawal(event: FormEvent) {
    event.preventDefault();
    setBusy('withdraw'); setError(''); setNotice('');
    try {
      await post('/finance/withdrawals/', {method: withdrawForm.method, amount: withdrawForm.amount, account_number: withdrawForm.account});
      setWithdrawForm({...withdrawForm, amount: ''});
      setNotice('Withdrawal requested. The payout goes to the number you entered after review.');
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'The withdrawal could not be requested.');
    } finally { setBusy(''); }
  }

  const methods = summary?.payment_methods ?? [{value: 'bkash', label: 'bKash'}, {value: 'nagad', label: 'Nagad'}, {value: 'rocket', label: 'Rocket'}];
  const canWithdraw = summary?.can_withdraw ?? false;

  return <PortalShell title="Finance" eyebrow="Your money on Venus">
    {error && <p className="form-error" role="alert">{error}</p>}
    {notice && <p className="success" role="status">{notice}</p>}

    {loading && !summary ? <LearnerLoading label="Loading your balance…"/> : <div className="finance-stack">
      <section className="finance-band" aria-label="Account summary">
        <div className="finance-balance">
          <span className="eyebrow">Available balance</span>
          <b className="finance-amount">{summary ? money(summary.balance) : '—'}</b>
          <small>Used for mentor sessions, course fees and payouts on Venus Learning.</small>
        </div>
        <dl className="finance-facts">
          <div><dt>Top-ups waiting for verification</dt><dd>{summary?.pending_top_ups ?? 0}</dd></div>
          <div><dt>Approved top-ups</dt><dd>{summary ? money(summary.approved_top_ups) : '—'}</dd></div>
          {canWithdraw && <div><dt>Paid out to you</dt><dd>{summary ? money(summary.paid_withdrawals) : '—'}</dd></div>}
          {canWithdraw && <div><dt>Withdrawals pending</dt><dd>{summary?.pending_withdrawals ?? 0}</dd></div>}
        </dl>
      </section>

      <div className="finance-split">
        <section className="panel" aria-labelledby="top-up-heading">
          <div className="panel-head"><h2 id="top-up-heading">Top up</h2><span className="tag">bKash · Nagad · Rocket</span></div>
          <p className="muted">Send the amount from your mobile wallet first, then submit the receipt details here. Balance is credited after we match the transaction ID.</p>
          <form onSubmit={submitTopUp}>
            <fieldset className="finance-methods"><legend>Payment service</legend>
              {methods.map(method => <label key={method.value} className={topUpForm.method === method.value ? 'method-chip active' : 'method-chip'}>
                <input type="radio" name="top-up-method" value={method.value} checked={topUpForm.method === method.value} onChange={() => setTopUpForm({...topUpForm, method: method.value})}/>
                {method.label}
              </label>)}
            </fieldset>
            <div className="form-grid">
              <div className="field"><label htmlFor="topup-amount">Amount sent (Tk)</label><input id="topup-amount" type="number" min="1" step="0.01" required value={topUpForm.amount} onChange={e => setTopUpForm({...topUpForm, amount: e.target.value})}/></div>
              <div className="field"><label htmlFor="topup-account">Your {methods.find(m => m.value === topUpForm.method)?.label} number</label><input id="topup-account" inputMode="numeric" autoComplete="tel" required placeholder="01712345678" value={topUpForm.account} onChange={e => setTopUpForm({...topUpForm, account: e.target.value})}/></div>
            </div>
            <div className="field"><label htmlFor="topup-transaction">Transaction ID from the receipt</label><input id="topup-transaction" required autoComplete="off" placeholder="e.g. BKH8J2K9QW" value={topUpForm.transaction} onChange={e => setTopUpForm({...topUpForm, transaction: e.target.value})}/></div>
            <div className="actions"><button className="btn btn-primary" disabled={busy === 'top-up'}>{busy === 'top-up' ? 'Submitting…' : 'Submit top-up'}</button></div>
          </form>
        </section>

        {canWithdraw ? <section className="panel" aria-labelledby="withdraw-heading">
          <div className="panel-head"><h2 id="withdraw-heading">Withdraw</h2><span className="tag">Instructors only</span></div>
          <p className="muted">Your teaching earnings can be sent to your own bKash, Nagad or Rocket number. The amount is deducted when the payout is completed.</p>
          <form onSubmit={submitWithdrawal}>
            <fieldset className="finance-methods"><legend>Payout service</legend>
              {methods.map(method => <label key={method.value} className={withdrawForm.method === method.value ? 'method-chip active' : 'method-chip'}>
                <input type="radio" name="withdraw-method" value={method.value} checked={withdrawForm.method === method.value} onChange={() => setWithdrawForm({...withdrawForm, method: method.value})}/>
                {method.label}
              </label>)}
            </fieldset>
            <div className="form-grid">
              <div className="field"><label htmlFor="withdraw-amount">Amount (Tk)</label><input id="withdraw-amount" type="number" min="1" step="0.01" required value={withdrawForm.amount} onChange={e => setWithdrawForm({...withdrawForm, amount: e.target.value})}/></div>
              <div className="field"><label htmlFor="withdraw-account">Receiving {methods.find(m => m.value === withdrawForm.method)?.label} number</label><input id="withdraw-account" inputMode="numeric" autoComplete="tel" required placeholder="01912345678" value={withdrawForm.account} onChange={e => setWithdrawForm({...withdrawForm, account: e.target.value})}/></div>
            </div>
            <div className="actions"><button className="btn btn-primary" disabled={busy === 'withdraw'}>{busy === 'withdraw' ? 'Requesting…' : 'Request withdrawal'}</button></div>
          </form>
        </section> : <section className="panel finance-note" aria-labelledby="withdraw-note-heading">
          <div className="panel-head"><h2 id="withdraw-note-heading">Withdrawals</h2></div>
          <p>Withdrawals are for instructors who teach on Venus Learning. Your sessions with a mentor are paid from this balance after the session ends.</p>
          <p className="muted">Teaching here? Your instructor account can request a payout to bKash, Nagad or Rocket from this page.</p>
        </section>}
      </div>

      <section className="panel" aria-labelledby="topup-history-heading">
        <div className="panel-head"><h2 id="topup-history-heading">Top-up requests</h2></div>
        {topUps.length ? <div className="table-wrap"><table className="table">
          <thead><tr><th>Submitted</th><th>Service</th><th>From</th><th>Transaction ID</th><th>Amount</th><th>Status</th></tr></thead>
          <tbody>{topUps.map(row => <tr key={row.id}>
            <td>{localTime(row.created_at)}</td><td>{row.method_label}</td><td>{row.account_number}</td><td>{row.transaction_id}</td>
            <td className="num">{money(row.amount)}</td>
            <td><span className={`tag ${statusClass(row.status)}`}>{row.status_label}</span>{row.review_note && <small className="muted verdict">{row.review_note}</small>}</td>
          </tr>)}</tbody>
        </table></div> : <LearnerEmpty>No top-ups yet. Submit your first one above.</LearnerEmpty>}
      </section>

      {canWithdraw && <section className="panel" aria-labelledby="payout-history-heading">
        <div className="panel-head"><h2 id="payout-history-heading">Withdrawal requests</h2></div>
        {withdrawals.length ? <div className="table-wrap"><table className="table">
          <thead><tr><th>Requested</th><th>Service</th><th>To</th><th>Amount</th><th>Status</th></tr></thead>
          <tbody>{withdrawals.map(row => <tr key={row.id}>
            <td>{localTime(row.created_at)}</td><td>{row.method_label}</td><td>{row.account_number}</td>
            <td className="num">{money(row.amount)}</td>
            <td><span className={`tag ${statusClass(row.status)}`}>{row.status_label}</span>{row.review_note && <small className="muted verdict">{row.review_note}</small>}</td>
          </tr>)}</tbody>
        </table></div> : <LearnerEmpty>No withdrawals yet. Your first payout request will appear here.</LearnerEmpty>}
      </section>}

      <section className="panel" aria-labelledby="ledger-heading">
        <div className="panel-head"><h2 id="ledger-heading">Account history</h2></div>
        {ledger.length ? <div className="table-wrap"><table className="table">
          <thead><tr><th>Date</th><th>Entry</th><th>Amount</th><th>Status</th><th>Details</th></tr></thead>
          <tbody>{ledger.map(entry => <tr key={entry.id}>
            <td>{localTime(entry.created_at)}</td><td>{entry.kind_label}</td>
            <td className={Number(entry.amount) < 0 ? 'num debit' : 'num credit'}>{money(entry.amount)}</td>
            <td><span className={`tag ${statusClass(entry.status)}`}>{entry.status_label}</span></td>
            <td className="muted">{entry.note}</td>
          </tr>)}</tbody>
        </table></div> : <LearnerEmpty>Nothing has moved through your account yet.</LearnerEmpty>}
      </section>
    </div>}
  </PortalShell>;
}
