import {NextRequest,NextResponse} from 'next/server';

export function proxy(request:NextRequest) {
  const nonce=Buffer.from(crypto.randomUUID()).toString('base64');
  const development=process.env.NODE_ENV==='development';
  const policy=[
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${development?" 'unsafe-eval'":''}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' https: data: blob:",
    "media-src 'self' https:",
    "font-src 'self'",
    `connect-src 'self'${development?' ws: wss:':''}`,
    "frame-src https://www.youtube-nocookie.com https://www.youtube.com https://player.vimeo.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; ');
  const headers=new Headers(request.headers);
  headers.set('x-nonce',nonce);
  headers.set('Content-Security-Policy',policy);
  const response=NextResponse.next({request:{headers}});
  response.headers.set('Content-Security-Policy',policy);
  response.headers.set('Cache-Control','private, no-store');
  return response;
}
export const config={matcher:['/((?!api|_next/static|_next/image|favicon.ico).*)']};
