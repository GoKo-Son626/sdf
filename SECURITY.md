# Security Policy

## Supported versions

SDF Translator is still in early development. Security fixes are provided only for the latest revision on `main`; older commits and third-party forks are not maintained separately.

## Reporting a vulnerability

Please use GitHub private vulnerability reporting from the repository's Security page. If that option is unavailable, open a minimal issue that contains no credentials, source documents, exploit code, or other sensitive details and ask the maintainer for a private contact channel.

A useful report may include:

- the affected version or commit;
- the issue category and potential impact;
- minimal reproduction steps using synthetic data;
- a suggested mitigation or fix.

Never submit real API keys, tokens, passwords, private keys, proxy credentials, private documents, or vocabulary files.

## Third-party services

Selected text is sent to the model provider configured by the user. If that request fails, it may be sent to a keyless machine-translation fallback. Those providers control their own data handling. Users remain responsible for following their organization's confidentiality requirements and each provider's privacy policy.
