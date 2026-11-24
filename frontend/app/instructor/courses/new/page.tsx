'use client';
import {useState} from 'react';
import {useRouter} from 'next/navigation';
import PortalShell from '../../../../components/PortalShell';
import AssetUpload from '../../../../components/AssetUpload';
import {post} from '../../../../lib/api';

export default function NewCourse(){
  const router=useRouter();
  const [f,setF]=useState({title:'',description:'',category:'',level:'',thumbnail:''});
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  const save=async(e:any)=>{
    e.preventDefault();
    setBusy(true);
    try{
      const c:any=await post('/courses/',f);
      router.push(`/instructor/courses/${c.id}`);
    }catch(x){
      setError((x as Error).message);
    }finally{
      setBusy(false);
    }
  };
  return <PortalShell title="Create course" role="Instructor">
    <form className="panel" onSubmit={save}>
      <p className="muted">Start a draft, then add units and lessons.</p>
      {error&&<div className="form-error">{error}</div>}
      {Object.keys(f).filter(k=>k!=='thumbnail').map(k=><div className="field" key={k}>
        <label>{k}</label>
        {k==='description'
          ? <textarea rows={6} required value={(f as any)[k]} onChange={e=>setF({...f,[k]:e.target.value})} />
          : <input required={k==='title'} type="text" value={(f as any)[k]} onChange={e=>setF({...f,[k]:e.target.value})} />}
      </div>)}
      <div className="field">
        <label>Thumbnail</label>
        <AssetUpload purpose="thumbnail" onUploaded={(url)=>setF({...f,thumbnail:url})} />
        {f.thumbnail&&<img src={f.thumbnail} alt="Course thumbnail preview" style={{width:'100%',maxWidth:320,borderRadius:12,marginTop:8}} />}
        <small className="muted">Upload an image file, or paste an image link below as a fallback.</small>
        <input type="url" placeholder="https://… (optional link fallback)" value={f.thumbnail} onChange={e=>setF({...f,thumbnail:e.target.value})} />
      </div>
      <button className="btn btn-primary" disabled={busy}>{busy?'Creating…':'Create draft'}</button>
    </form>
  </PortalShell>;
}
