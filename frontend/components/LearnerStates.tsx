'use client';

export function LearnerLoading({label = 'Loading…'}: {label?: string}) {
  return <div className="empty" role="status">{label}</div>;
}

export function LearnerError({message, retry}: {message: string; retry?: () => void}) {
  return <div className="empty" role="alert"><strong>Unable to load this right now.</strong><p>{message}</p>{retry && <button className="btn btn-soft" onClick={retry}>Try again</button>}</div>;
}

export function LearnerEmpty({children}: {children: React.ReactNode}) {
  return <div className="empty">{children}</div>;
}
