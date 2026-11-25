'use client';
import RoleLoginForm from '../../../components/RoleLoginForm';

export default function InstructorLogin() {
  return (
    <RoleLoginForm
      role="instructor"
      eyebrow="Instructor portal"
      title="Sign in to teach"
      subtitle="Manage your courses and learners."
      destination="/instructor"
      otherHref="/login/learner"
      otherRole="learner"
    />
  );
}
