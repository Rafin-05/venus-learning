'use client';
import RoleLoginForm from '../../../components/RoleLoginForm';

export default function LearnerLogin() {
  return (
    <RoleLoginForm
      role="learner"
      eyebrow="Learner portal"
      title="Sign in to learn"
      subtitle="Continue where you left off."
      destination="/dashboard"
      otherHref="/login/instructor"
      otherRole="instructor"
    />
  );
}
