# Privacy, local files and optional AI

Applies to the inspected PY.cad 16.5.0 desktop source. Reviewed 19 October 2026 (India).

## Local operation

Drawing documents, recovery snapshots, preferences and logs are stored on the
user's computer. PY.cad's inspected application code does not include an
analytics or advertising SDK, account system, or automatic drawing-upload
service. This is a code-review statement, not a guarantee about the operating
system, plugins, dependencies, future modifications, or a user-configured host.

Application settings and data locations follow the platform and the existing
legacy PyCAD settings/logging configuration. Recovery files and backups may contain
drawing data. Diagnostic logs can contain file paths, environment details and
error messages. Inspect logs before sharing them. Deleting the app does not
necessarily remove saved drawings, backups or installation logs.

## Setup and external connections

Setup connects to upstream download/package services (including GitHub and
PyPI) to obtain dependencies; on Windows it may contact Microsoft for its
runtime. The OS package manager may contact its repositories. Those services
receive ordinary request/network information under their own terms. The setup
progress page uses a temporary authenticated server on 127.0.0.1 and loads its
logo/legal page locally; it is not a public CAD service.

Opening external links from legal/help material starts the user's browser and
contacts the chosen site. User-installed DWG converters and other external
tools have separate privacy, licensing and security terms.

## AI interaction

Offline drafting chat commands do not require a cloud model. AI-provider requests
occur when the user explicitly chooses that mode and sends an instruction.
There are two workflows:

- The drawing-proposal dialog sends the instruction, drawing units and selected
  supported entity geometry to the configured endpoint. Its API-key field is
  cleared when the dialog closes; running request objects may remain in memory.
- Drafting chat sends the instruction, up to ten recent chat entries, levels and
  current level, bounded object IDs/types/bounds/properties (up to 250 objects),
  material names, quantity summaries/rates where applicable, and up to 100 selected
  entities with geometry/properties. Context is bounded in size. It can include
  information beyond the current selection, so review the whole drawing's
  confidentiality before using AI-provider mode. The configured API key stays in
  app-session memory; endpoint/model preferences persist. Chat history is held in
  session memory separately from saved drawings.

Remote endpoints require HTTPS; HTTP is allowed only for loopback local models.
Redirects are rejected. Responses are validated and proposed changes are shown
for review before applying supported actions. The app does not execute arbitrary
provider Python/shell code or include model weights or a provider subscription.

The inspected clients do not intentionally persist API keys to preferences,
drawings or exports. This is not a guarantee of secure memory erasure or of the
provider's logging/retention. AI services/models have separate terms, licenses
and possible charges. Obtain authorization before transmitting client plans,
personal data, addresses, credentials or commercially sensitive information.

## Optional WebDAV

Cloud upload/download is an explicit user action to a user-configured WebDAV
collection. Uploads can contain complete selected drawing files or requested
exports, not just geometry summaries. The endpoint and username can be retained
in preferences; the password is held for the dialog/session and cleared on close.
The chosen server has its own data handling, access and retention policies.
Remote connections require HTTPS; loopback HTTP is allowed for local development.

## Deployment responsibilities

A company hosting an AI endpoint, adding accounts/telemetry, collecting logs,
or distributing a modified hosted service must publish its actual operator
identity/contact, purposes, lawful basis where required, recipients, retention,
cross-border transfer arrangements and applicable user-rights process. This
local desktop notice does not claim GDPR, India's data-protection law, or every
other national privacy law compliance. Applicability depends on facts and may
require local legal review. The EU GDPR text is at
https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng .

For the present unhosted desktop package, seek privacy/support contact details
from the party that supplied your copy. No nonexistent controller or contact
address is asserted here.
