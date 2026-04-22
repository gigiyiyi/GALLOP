## GALLOP MVP Retention Policy

GALLOP MVP is a temporary workspace for preparing, reviewing, and exporting compliance packages. It is not a permanent archive or records-management system.

### What The App Is For

- Build a package from transactions, geo anchors, nodes, evidence, and risk inputs.
- Review, correct, and finalize the package during an active workflow window.
- Export the final package for downstream review and for the user's own retention.

### What The App Is Not For

- Long-term storage of packages or evidence.
- Permanent audit custody on behalf of users.
- Ongoing document-rights administration after the active workflow ends.

### User Retention Responsibility

Users are expected to retain exported packages outside the application:

- in a designated email account from a major provider, and/or
- in local or organizational storage where available.

The exported ZIP package is the durable handover artifact. The in-app workspace is temporary.

### MVP Retention Windows

- Active records may remain in the app while they are being worked on.
- Records are retained for a short working period after the last activity.
- Resolved review metadata should be retained for a shorter period than core package data.
- Expired workspace data may be deleted from the application without long-term recovery guarantees.

### Default MVP Technical Policy

- Records in `draft`, `submitted`, or `sealed` state are eligible for purge after `30 days` of inactivity.
- Short-lived review or correction metadata should be purged sooner when implemented.
- Files stored under `data_files/` are deleted together with their expired record.

### User-Facing Notice

Recommended notice in the app:

> This application is a temporary workspace for preparing and reviewing compliance packages. It does not provide long-term storage. Please retain exported packages in your designated email account and, where available, in local or organizational storage.
