# Moving from LearnSpace to Venus Learning

## What the archive contains

The supplied SQL file defines the legacy tables and inserts a default administrator. It does not contain real learner/instructor accounts, courses, enrollments, attempts, certificates, or learning history to migrate. This rebuild therefore supplies a clean schema and an explicitly opt-in local sample-data command, not fabricated historical records.

The old SQL dump, hard-coded database credentials, default administrator password, PHP code, and Git history are not part of the release. The source archive remains separate from this package.

## If a live legacy database exists elsewhere

Back it up before doing anything. Export a sanitized copy into a restricted migration environment; never upload production passwords or learner records into a public repository. No automatic live-data importer is claimed in this handoff because no such data was supplied or tested.

The receiving developer should map separate legacy user/instructor/admin IDs into the new `User` model, recording source table plus source ID to avoid collisions. Map course owners, units and ordered lessons, enrollments/progress, reviews, quiz questions and attempts, contests and participants, ranked prize labels, coding problems/completions, certificates, and support messages/replies. Preserve original timestamps and certificate identifiers where policy permits, and check all foreign keys and unique constraints.

Do not copy PHP password hashes into Django's password column as if they were compatible. Use a reviewed transitional hasher only when the exact old algorithm is known, or require a verified password reset. Reconfirm administrator privileges and instructor approvals; do not infer trust from an imported email address alone.

Legacy HTML, file paths, and third-party embeds need a separate content review. Rebuild plain-text lessons or sanitize with a reviewed allowlist converter; never render imported HTML directly. Re-upload approved raster images and PDFs through the new authenticated upload flow. Reconcile unsupported file formats and video hosts explicitly rather than exposing old upload directories.

## Migration acceptance

Compare record counts and sampled records, ownership, completion percentages, grades, ranks, prize labels, support replies, and certificate numbers. Test sign-in/reset with representative accounts and verify that learners cannot see private material or answer keys. Keep the old site read-only during cutover, document rollback, and retain the backup until the new system has been accepted.
