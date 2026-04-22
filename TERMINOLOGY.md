## GALLOP MVP Terminology

This glossary keeps core product language stable across English, Chinese, and future UI languages such as Thai, Bahasa Indonesia, and French.

### Core Terms

- `Record`
  - Meaning: the full compliance workspace/package for one case.
  - Notes: use one stable equivalent in each language; do not mix with case, file, and package randomly.

- `Source-fact`
  - Meaning: the stricter anchored mode where facts must be linked to concrete supporting objects before sealing.
  - Preferred display:
    - English: `Fact-Anchored (Source-fact)`
    - Chinese: `事实锚定（Source-fact）`
  - Notes: keep the English term visible in early versions until users are comfortable with the localized term.

- `Narrative`
  - Meaning: the more flexible mode where the package can still be built and submitted with lighter anchoring.
  - Preferred display:
    - English: `Narrative`
    - Chinese: `叙述模式（Narrative）`
  - Notes: avoid wording that makes it sound informal or unreliable.

- `Node`
  - Meaning: a company, operator, site, or trading/processing actor involved in the supply chain.
  - Preferred display:
    - English: `Supply Chain Entity`
    - Chinese: `企业 / 运营节点`
  - Notes: keep this distinct from user accounts.

- `Geo Anchor`
  - Meaning: a geographic reference or source-area location used to anchor evidence and transactions.
  - Preferred display:
    - English: `Source Location`
    - Chinese: `源头位置 / 地理锚点`
  - Notes: use wording that covers point, polygon, and symbolic references.

- `Evidence`
  - Meaning: a supporting file or document attached to a transaction, node, geo anchor, or batch-system target.
  - Preferred display:
    - English: `Supporting Document`
    - Chinese: `支持性文件 / 证据`
  - Notes: do not switch between document, proof, and attachment without a reason.

- `Batch System`
  - Meaning: the production or segregation control system used to keep material traceable and govern mixing.
  - Preferred display:
    - English: `Batch-Control System`
    - Chinese: `批次控制系统`
  - Notes: keep this term operational rather than overly technical.

- `Submit`
  - Meaning: finalize and hand off a narrative record.
  - Notes: distinct from seal.

- `Seal`
  - Meaning: lock a source-fact record as a filed package.
  - Notes: use wording that clearly implies locking/finalization.

- `Downgrade`
  - Meaning: move a source-fact draft into narrative mode while preserving history and reason.
  - Notes: do not translate this in a way that sounds like data loss.

### Translation Rules

- Keep all internal codes in English:
  - DB columns
  - status values
  - mode values
  - evidence type codes
  - rule IDs

- Translate only user-facing text:
  - labels
  - buttons
  - guidance
  - captions
  - warnings
  - help text

- English is the fallback language for missing translations.
