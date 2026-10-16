# EventLens disclosure review: observed design and interface contract

Reviewed October 13, 2026 (America/New_York). This is a description of the existing review surface, not a repository-wide product or design specification.

## Overview

The disclosure-review page extends Nick's pinned AiHTMLs academic visual system: white paper, serif text, a centered title and italic subtitle, numbered sections, horizontal rules, and restrained accent color. Its purpose on this surface is to let a human inspect two saved disclosures, record numerical labels and evidence, and export a review record. It is an operational form within that existing visual system.

Evidence inspected:

- Global rules in `/Users/nickzhu/.claude/CLAUDE.md` and project instructions in `HANDOVER.md`.
- `docs/earnings_experiment.md` and the retained private `docs/earnings_change_spec.md`.
- Builder: `scripts/earnings_review.py`.
- Generated page: `/Users/nickzhu/Desktop/Library/AiHTMLs/Projects/EventLens/disclosure-review.html`.
- Incumbent library: `/Users/nickzhu/Desktop/Library/AiHTMLs/index.html`.
- Saved images in this directory: `desktop.jpg` (1425 × 2152 pixels) and `mobile.jpg` (375 × 4070 pixels).
- Validation source: `tests/review_page_checks.cjs`, read but not executed during this documentation pass.

The artifact's inline CSS is byte-for-byte identical to the builder's CSS. The images were saved after the inspected builder and artifact. Their visible controls, initial Adobe pair, typography, and responsive layout agree with the source. File times establish ordering, not browser provenance or a complete visual-regression guarantee.

The context launcher had already failed with permission denied in the parent task. Existing files were used directly; the launcher was not retried. `PRODUCT.md`, `DESIGN.md`, and `.impeccable/design.json` are absent. The existing artifact and the user's pinned style provide sufficient authority for this bounded documentation pass. No new visual identity, product context, root design file, or sidecar was created.

## Colors

These are observed source values, not a proposed palette.

| CSS value | Role |
| --- | --- |
| `--ink: #20201e` | Body text and strongest horizontal rules |
| `--muted: #575754` | Labels, subtitle, source metadata, footer |
| `--line: #bfbfba` | Field borders and light separators |
| `--accent: #254f6b` | Links, buttons, normal status text, keyboard focus |
| `--wash: #f5f5f1` | Source text and quotation backgrounds; secondary-button hover |
| `--error: #8b2424` | Error status text |
| `#fff` / `white` | Page and input backgrounds; primary-button text |
| `#d9e8f0` | Selected text background |
| `#8a8a84` | Source scrollbar thumb, where supported |

The library index uses closely related dark ink, muted gray, and blue link colors. The review surface preserves that relationship while using local values; it does not share a token file with the index.

Calculated contrast from the source sRGB values: ink on white 16.32:1, muted text on white 7.25:1, muted text on the wash 6.63:1, accent on white 8.72:1, error text on white 8.84:1, and ink on the wash 14.93:1. These text pairs have strong contrast. The input/separator color against white is 1.85:1; input boundaries are a specific accessibility concern where they are needed to identify a control. This pass did not repair that color or claim overall accessibility conformance.

## Typography

| Role | Observed CSS |
| --- | --- |
| Body | `17px/1.55 Georgia, 'Times New Roman', serif` |
| Page title | `30px`, line-height `1.2`; `26px` at the mobile breakpoint |
| Subtitle | Inherited serif; centered, italic, muted |
| Section heading | `22px` |
| Source heading | `19px` |
| Labels, status, quotation list | `15px` |
| Metadata and footer | `14px` |
| Source text | `15px/1.55 Georgia, serif`, preserving whitespace and wrapping |
| Textareas | `15px/1.4`, inherited serif |

Native controls inherit the page font before their role-specific overrides. Paragraphs have a `75ch` maximum width. The index begins its font stack with Latin Modern Roman and Computer Modern Serif; this page begins with Georgia. That is an observed implementation difference within the prescribed serif style, not permission to standardize all library fonts.

## Layout

- The desktop page is centered, with maximum width `1500px` and padding `34px 4vw 70px`.
- Navigation is a wrapping flex row with a `12px` gap. The case selector takes extra available space; Previous, Next, and reviewed-count controls follow it.
- Previous and current disclosure panels use equal grid columns with a `28px` gap. Each has source identity, a window selector, a scrolling text region, numerical fields, evidence textareas, quotation actions, and a source hash.
- Numerical fields use three columns with a `10px` gap. Judgment fields use three columns with a `14px` gap. Action groups wrap with an `8px` gap.
- At `max-width: 760px`, body padding becomes `24px 18px`; source panels and judgment fields become single-column; numerical fields use two columns; the case selector occupies a full row; navigation buttons expand.
- Source text regions have `330px` height on desktop and `270px` below the breakpoint, with internal scrolling. Text, identifiers, and hashes can wrap within their containers.

The desktop image shows both disclosures aligned side by side and a clearly separated judgment section. The mobile image shows the complete previous disclosure followed by the complete current disclosure, then judgment and export actions. The visible page fits its image width, with wrapped hashes and buttons; no page-level horizontal clipping is apparent. The longer mobile reading path is the implemented consequence of stacked source panels.

The first displayed guidance windows in both images begin with contact information. The old source window reaches a release-title sentence near the bottom, while the current window still shows contact details. The populated revenue quotations remain visible below the windows. This is a source-window relevance issue to retain as an observation; a screenshot cannot establish how other windows or cases behave.

## Elevation & Depth

The surface is flat. There are no authored shadows, gradients, floating overlays, sticky panels, or animations. Horizontal rules establish hierarchy; the pale wash separates source text from editable form fields. The main toolbar and judgment section use stronger `2px` ink rules, while source sections and the footer use lighter `1px` lines.

## Shapes

The visible form is rectangular and restrained. The stylesheet does not define a border-radius scale; native browser control styling may vary. Buttons have a `1px` accent border and `8px 13px` padding, with `42px` minimum height. Inputs, selects, and textareas have `1px` light borders and `7px` padding. Textareas have `95px` minimum height and vertical resizing. The attestation checkbox is `20px` square and sits within its full text label.

## Components

### Navigation and source evidence

The disclosure selector and Previous/Next buttons select one pair at a time. Navigation disables the unavailable direction at the first and last pairs. The reviewed counter is derived from row state, although its denominator is the literal value `36` in the current builder. The embedded artifact contains 36 pairs, 12 issuers, and 50 source records, matching the current footer counts. Those literals will need an intentional update if the corpus size changes.

Source links include the saved source ID and publication date and open the external source in a new tab with `rel="noopener"`. Each panel offers candidate guidance windows and the full saved release. Source text is a focusable, named `<pre>` region. A selection can fill the revenue quote or heading quote, or add a management-explanation quotation. Both mouse and keyboard selection events are handled in source; mobile selection behavior was not tested here.

### Numerical and judgment fields

Each source has label status, currency, unit, bounds, basis, and exact evidence fields. Guidance withdrawal disables and empties the bounds; abstention retains no metric for that source. The judgment section records direction, explanation availability, conflict judgment, notes, reviewer name, and personal attestation.

Visible labels wrap their fields. Generated source-window selectors and source regions receive accessible names. The primary action is the filled accent button, “Mark this pair reviewed”; secondary actions preserve pending state, export JSON, or restore JSON.

### Review state and persistence

The implemented contract is explicit human review: completing form fields alone does not count as review. Approval checks a name, personal attestation, required judgments and notes, quotation membership, numerical compatibility, and direction consistency. It then records reviewer identity and time. Changes to saved label/judgment fields reopen the row as pending and clear its review identity, timestamp, and attestation.

Drafts save to browser local storage. Export includes schema, source hashes, and the case records. Restore validates the corpus and reviewed-row consistency before replacing in-memory rows. Status and error messages use text and `role="status"` with polite live announcements. Two status regions exist: the save/review state near the top and action feedback after the review controls.

### Accessibility evidence and limits

- A visible keyboard focus rule uses a `2px` accent outline with `3px` offset. Browser keyboard traversal and focus after re-render were not exercised in this pass.
- Native buttons, selects, inputs, labels, headings, navigation, and status roles provide a useful semantic foundation. No screen-reader session was conducted.
- Errors have explanatory text as well as color. The action-feedback region is near the bottom of the page; source-selection errors can therefore be distant from the source action that triggered them. The code does not move focus to that feedback region.
- Buttons have a defined minimum height; the attestation control has a surrounding text label. Pointer target geometry, touch selection, and platform-specific native control behavior were not measured.
- The page embeds its data, CSS, and JavaScript and declares no external script, stylesheet, or image dependencies. Opening a source link still uses the external issuer/SEC page. Storage and download permissions remain browser-dependent.
- The existing JavaScript test file covers selected validation functions using a VM, not a rendered browser. It is not evidence of keyboard, screen-reader, touch, zoom, or responsive interaction coverage, and was not rerun here.

## Do's and Don'ts

- **Do** preserve the user-prescribed white academic surface, serif reading typography, centered title/italic subtitle, numbered sections, restrained color, and horizontal-rule hierarchy when extending this page.
- **Do** keep the previous/current source identity, exact evidence, label state, reviewer attestation, and export path legible. Preserve the distinction between a draft and a human-reviewed record.
- **Do** keep generated HTML in the AiHTMLs library and maintain its catalog entry when adding an artifact. The current index already lists this page in Projects · EventLens with count `(1)`.
- **Do** recheck local tokens and corpus literals if the builder changes. This report describes the inspected snapshot.
- **Don't** infer a new project-wide brand, product strategy, or redesign mandate from missing context files.
- **Don't** treat screenshots or literal quote validation as proof of semantic label correctness or completed human review.

### Existing context drift, left unchanged

`HANDOVER.md` retains the earlier three-pair starting statuses and milestone plan. The original earnings specification also retains historical planning and pilot language. `docs/earnings_experiment.md` now explicitly identifies its three-pair material as the original pilot and points to the 36-pair M1/M3 checkpoint. The generated review page and library entry describe the newer 36-pair surface. These documents have different time scopes; this pass did not reconcile or rewrite them.

### Verification boundary and snapshot identity

This pass inspected static source, compared artifact/builder CSS, computed color contrast, and visually examined the two existing images. It did not launch a browser, exercise form controls, write browser state, create review records, rerun tests, fetch external sources, incur model costs, or modify the UI. There is no saved viewport/DPR/browser manifest alongside the images; only their pixel dimensions and file ordering are established here. Intermediate widths, zoom, alternative browsers, validation error states, withdrawal state, long quotation states, and restored/reviewed states were not visually verified.

| Inspected file | Modification time (UTC) | SHA-256 |
| --- | --- | --- |
| `scripts/earnings_review.py` | `2026-10-14T00:59:29.588036+00:00` | `49694069807fd254ad392a48fbf9767d1baefd24020ed9fd4bc09f90150bd121` |
| `disclosure-review.html` | `2026-10-14T00:59:29.936890+00:00` | `83fbc3bc22abd98f5a6a7aa0bf832f1d4f42de808a35b295327e03ce5cc65ac8` |
| `desktop.jpg` | `2026-10-14T01:00:21.230312+00:00` | `51f8d552448a4d008499a58131c8345397f908586f5176bddf88337a0b69ab61` |
| `mobile.jpg` | `2026-10-14T01:00:22.410346+00:00` | `319f00785cc769fbc33e299ffff9a2196fbf155d2d3d458f047ffcee9b155dd9` |

Only this report was written by the documentation pass.
