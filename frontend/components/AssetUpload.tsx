'use client';
import {useState} from 'react';
import {api} from '../lib/api';
export default function AssetUpload({purpose,course,onUploaded}:{purpose:'avatar'|'thumbnail'|'document';course?:number;onUploaded:(url:string)=>void}) {
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 async function upload(event:React.ChangeEvent<HTMLInputElement>) {
  const file=event.target.files?.[0];if(!file)return;setError('');
  if(file.size>5*1024*1024){setError('Choose a file smaller than 5 MiB.');return;}
  setBusy(true);
  try {
   const body=new FormData();body.append('file',file);body.append('purpose',purpose);if(course)body.append('course',String(course));
   const data=await api<{url:string}>('/uploads/',{method:'POST',body});
   onUploaded(data.url);
  } catch(err){setError(err instanceof Error?err.message:'Upload failed.');}finally{setBusy(false);event.target.value='';}
 }
 return <div className="field"><label className="btn btn-soft">{busy?'Uploading…':`Upload ${purpose}`}<input type="file" hidden accept={purpose==='document'?'.pdf,application/pdf':'image/jpeg,image/png,image/webp'} onChange={upload} disabled={busy}/></label><small className="muted">{purpose==='document'?'PDF download':'JPEG, PNG, or WEBP; re-encoded to PNG'} · up to 5 MiB{purpose==='thumbnail'?'. Changing a thumbnail sends the course for review.':''}</small>{error&&<p className="form-error" role="alert">{error}</p>}</div>;
}
