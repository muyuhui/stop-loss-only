## 1. Extension settings and persistence

- [ ] 1.1 Confirm the three prerequisite changes are archived and their complete gates pass.
- [ ] 1.2 Add ordered migrations for delivery attempts, channel metadata, import audit, and retention state.
- [ ] 1.3 Add grouped runtime settings for notifications, retention, import limits, and diagnostics.
- [ ] 1.4 Implement Windows machine-protected secret storage and masked settings responses.

## 2. Notification delivery

- [ ] 2.1 Create delivery attempts only after the alert transaction commits.
- [ ] 2.2 Implement stable delivery idempotency, timeout, bounded retry, and retry scheduling.
- [ ] 2.3 Implement HTTPS target normalization, DNS/IP revalidation, SSRF blocking, timestamp, and HMAC signing.
- [ ] 2.4 Implement minimal and explicitly expanded privacy payload levels with redacted logs.
- [ ] 2.5 Add explicit browser-notification permission UI and denied/unsupported fallback states.
- [ ] 2.6 Test rollback isolation, duplicate jobs, unsafe targets, secret redaction, and browser permission behavior.

## 3. Import, export, and history maintenance

- [ ] 3.1 Define the versioned standard holdings CSV schema and Decimal-safe encoding.
- [ ] 3.2 Implement bounded parsing, normalization, formula-injection defense, and zero-write preview tokens.
- [ ] 3.3 Implement expiring-token verification and atomic import commit with domain events.
- [ ] 3.4 Implement stable Decimal-safe position, lot, rule, and accounting exports.
- [ ] 3.5 Add import preview, per-row error, commit, and export flows to settings.
- [ ] 3.6 Implement configurable batched history cleanup with resumable progress.
- [ ] 3.7 Implement server-side chart downsampling that preserves key event points.
- [ ] 3.8 Test invalid and oversized files, expired previews, atomic failure, formula text, and Decimal round trips.

## 4. Backup, diagnostics, and final gates

- [ ] 4.1 Make backup names collision-safe and add schema, checksum, integrity, and WAL-aware manifest data.
- [ ] 4.2 Validate restore manifest, supported schema, target path, integrity, recovery point, and readiness auto-rollback.
- [ ] 4.3 Add a backup-only UI for the controlled directory while keeping restore as a stopped-service command.
- [ ] 4.4 Implement previewable privacy-safe diagnostics and database/retention size reporting.
- [ ] 4.5 Test same-second backups, incompatible manifests, damaged data, WAL state, and readiness rollback.
- [ ] 4.6 Run notification security, import/export, retention, backup/restore, frontend, build, offline smoke, and strict OpenSpec gates.
- [ ] 4.7 Document privacy defaults, browser delivery limits, standard CSV scope, recovery procedure, and independent feature disablement.
