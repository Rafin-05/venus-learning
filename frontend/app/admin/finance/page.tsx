'use client';
import {AdminPage,useCollection,Notice,Action,post} from '../_components';

function ReviewTable({path,kind,labels}:{path:string;kind:'top-ups'|'withdrawals';labels:Record<string,string>}) {
  const {data,loading,error,reload}=useCollection<any>(path);
  const review=async(id:number,action:'approve'|'reject')=>{await post(`${path}/${id}/${action}/`,{});reload()};
  const pending=data.filter(x=>x.status==='pending');
  return <div className="panel"><h2>{labels.title}</h2><p className="muted">{labels.subtitle}</p><Notice error={error}/>
  {loading?<p>Loading…</p>:pending.length?<div className="table-wrap"><table className="table"><thead><tr>{kind==='top-ups'&&<th>User</th>}{kind==='withdrawals'&&<th>Instructor</th>}<th>Amount</th><th>Method</th><th>Account</th>{kind==='top-ups'&&<th>Transaction ID</th>}<th>Submitted</th><th>Actions</th></tr></thead><tbody>
  {pending.map(x=><tr key={x.id}><td>{x.user_email}</td><td>৳ {x.amount}</td><td>{x.method_label}</td><td>{x.account_number}</td>{kind==='top-ups'&&<td>{x.transaction_id}</td>}<td>{x.created_at}</td><td><Action label="Approve" tone="primary" onClick={()=>review(x.id,'approve')}/>{' '}<Action label="Reject" onClick={()=>review(x.id,'reject')}/></td></tr>)}
  </tbody></table></div>:<p className="muted">No pending {kind==='top-ups'?'top-ups':'withdrawals'}.</p>}</div>;
}

export default function Finance(){
  return <AdminPage title="Finance review" eyebrow="Operations">
    <ReviewTable path="/finance/top-ups/" kind="top-ups" labels={{title:'Top-up verifications',subtitle:'Match each mobile-wallet transaction ID against the bKash, Nagad or Rocket merchant statement, then approve or reject.'}}/>
    <ReviewTable path="/finance/withdrawals/" kind="withdrawals" labels={{title:'Withdrawal payouts',subtitle:'Approving pays out to the instructor\'s mobile wallet and deducts it from their balance.'}}/>
  </AdminPage>;
}
