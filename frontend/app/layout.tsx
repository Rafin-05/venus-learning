import './globals.css';
import Link from 'next/link';
import AppNav from '../components/AppNav';
import {connection} from 'next/server';
export const metadata = {title:'Venus Learning | Learn with purpose',description:'Practical courses, coding practice, and learning challenges for your next chapter.'};
export default async function Layout({children}:{children:React.ReactNode}) {
  await connection();
  return <html lang="en"><body><AppNav/>{children}<footer className="footer"><div className="container footergrid"><div><img src="/venus-wordmark.png" alt="Venus Learning" className="footlogo"/><p>Learning that meets you where you are.</p></div><div><b>Learn with purpose</b><p><Link href="/courses">Course catalog</Link> · <Link href="/contests">Contests</Link> · <Link href="/profile">Account</Link></p></div></div></footer></body></html>;
}
