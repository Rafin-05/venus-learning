'use client';
import RoleLoginForm from '../../../components/RoleLoginForm';

export default function AdminLogin() {
  return (
    <RoleLoginForm
      role="admin"
      eyebrow="Admin portal"
      title="Sign in to manage"
      subtitle="Moderate courses, users and finance."
      destination="/admin"
      otherHref="/login/learner"
      otherRole="learner"
    />
  );
}
