# Verification emails not arriving

## The release defaults do not send email

The supplied `.env.example` sets `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`. If the deployment copied that value into `.env`, signup prints the verification email to the API container's logs instead of sending it to a mailbox. Signup can therefore report success without delivering an email. Password-reset emails behave the same way.

The example also leaves SMTP host and credentials blank and uses `no-reply@example.com` as a placeholder sender. The production Compose override does not change the email backend. This is confirmed from the source package, not from an inspected live deployment.

## Enable real delivery

Configure the deployed `.env` using the actual email provider's SMTP settings, for example:

```dotenv
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=YOUR_PROVIDER_SMTP_HOST
EMAIL_PORT=587
EMAIL_HOST_USER=YOUR_SMTP_USERNAME
EMAIL_HOST_PASSWORD=YOUR_SMTP_PASSWORD
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=Venus Learning <YOUR_VERIFIED_SENDER_ADDRESS>
FRONTEND_URL=https://YOUR_ACTUAL_SITE_DOMAIN
```

These are placeholders, not working credentials. Use a sender authorized by your provider. The existing application supports STARTTLS using `EMAIL_USE_TLS`; it does not currently expose Django's `EMAIL_USE_SSL` setting for implicit-TLS port 465. Choose a provider-supported STARTTLS endpoint or add explicit SSL support before using port 465.

Recreate both API services so they load the updated environment. For the production setup:

```sh
docker compose -f compose.yaml -f compose.production.yaml up -d --force-recreate api1 api2
```

For local HTTP Compose, omit `-f compose.production.yaml` and use `docker compose up -d --force-recreate api1 api2`.

Register a new test account using a mailbox you own. Confirm that the email arrives and its link opens the correct public domain, verifies the account, and permits sign-in. SMTP acceptance is not proof of inbox delivery: if SMTP is configured but messages still do not arrive, inspect provider delivery events, sender/domain authorization and the mailbox's spam folder.

## Accounts already registered

Changing SMTP settings does not automatically resend existing messages. After fixing email delivery, existing users should open `/resend-verification` (linked from sign-in, signup, and verification pages), enter the email they originally registered, and request a new link. They do not need to register again.

The CSRF-protected `POST /api/auth/resend-verification/` accepts `{email}` and uses a generic response to avoid revealing whether an account exists. Only active, unverified accounts can receive a new link. Source-IP limits and a per-account cooldown limit repeated sends. A newly issued link expires after two days and replaces previous unused verification links. A mail exception rolls back token changes, preserving any previous usable link. No instructor approval or mailbox verification is bypassed.

The confirmation deliberately does not prove that an email was delivered. If no message arrives after the cooldown, the operator must investigate SMTP/provider delivery rather than repeatedly creating accounts. For local evaluation only, an authorized operator can privately inspect `docker compose logs api1 api2` for console-backend emails. Never share these logs or verification tokens publicly.

## What is and is not verified

The registration code calls Django's mail sender, and its automated acceptance test checks the generated link using a mocked sender. Those tests do not establish real SMTP delivery. No live SMTP credentials, hosting configuration or provider delivery logs were available in the release ZIP, and no real verification email was sent during this investigation.
