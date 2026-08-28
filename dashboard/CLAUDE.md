# dashboard/ — UI/UX instructions

Scoped rules for this directory. Read the root [../CLAUDE.md](../CLAUDE.md) first, and the full spec at [../docs/UI-UX-REQUIREMENTS.md](../docs/UI-UX-REQUIREMENTS.md) before designing any new component — this file is the enforced subset, not a replacement.

## The one rule that governs everything here

The dispatcher is a tired human at 3am deciding who gets a boat first. Effects live on the chrome (panels, rails, transitions) and are forbidden between the dispatcher and the data. **If a choice makes the screen prettier and a district name harder to read, the district name wins.** (UI-UX §0.) Reject any change — your own or a review suggestion — that trades legibility for polish.

## Non-negotiables

**Tokens.** Every colour, radius, and shadow used anywhere in this directory must be one of the CSS custom properties already defined in `styles.css`'s `:root`. Never write a raw hex value, a raw `px` shadow, or an ad hoc border-radius in a `.html`/`.js`/`.css` file. If a new token is genuinely needed, add it to `styles.css` `:root` first, in the same style as the existing tokens (UI-UX §2.1/§4.1/§4.2) — don't invent one inline.

**Glass is scoped to exactly four surfaces:** the filter chip bar floating over the map, the map legend card, the map zoom/layer controls, and the toast stack. **Glass is banned** on the ticket table, the detail drawer body, any transcript, any input the dispatcher types into, and the TTT header — those stay `--paper` at full opacity, no exceptions (UI-UX §4.3). Wrap any `.glass` usage in `@supports (backdrop-filter: blur(1px))` with the documented fallback; never make layout depend on the blur rendering.

**State is never colour-only.** Every ticket/pin state (confirmed, unconfirmed, disputed, duplicate, unintelligible, unlocated) must be encoded in shape as well as colour, per the table in UI-UX §2.3. A colour-blind dispatcher or a washed-out projector must still be able to read every state.

**Urgency uses the fixed four-step temperature ramp** (`critical`/`high`/`moderate`/`info` → vermilion/marigold/indus/silt) from UI-UX §2.2. Never substitute a green "good" state — none of these tickets are good, and green breaks that signal.

**Typography is role-locked, not a style choice:**
- Archivo Expanded (600/700) — TTT header figure and panel titles only. Never body text.
- Public Sans — all UI and body text, and Roman Urdu content (it's Latin script, stays LTR, no font switch).
- IBM Plex Mono, tabular figures — every number: timers, P-codes, coordinates, quantities, confidence values. A live-updating number that isn't in Plex Mono will visibly jitter; that's the tell something's wrong.
- Noto Nastaliq Urdu, 18px, `line-height: 2.1` — Urdu-script transcript blocks only, in their own `direction: rtl; text-align: right` container. A normal 1.5 line-height clips Nastaliq descenders and a native reader notices immediately. Never truncate an Urdu line with a CSS ellipsis mid-word — clamp by line count instead. Mixed code-switched lines need `unicode-bidi: plaintext` so an embedded English word doesn't reverse the line.
- The dispatcher-facing chrome (labels, buttons, headers) is always English. Only sender content and outbound reply previews are Urdu/Roman Urdu.

**Motion carries state changes, never decorates them.** Use only the three easing variables already in `styles.css` (`--surge` for entrances/expansion, `--settle` for exits, `--snap` for small flips) and stay within the duration table in UI-UX §7.2 — nothing exceeds 400ms except a decay the dispatcher never waits on (e.g. the 1400ms arrival-glow fade). Respect `prefers-reduced-motion` (already stubbed in the spec) with its one stated exception: the arrival glow keeps a soft 300ms fade rather than snapping instantly, because a hard flash is worse for motion-sensitive users than a fade.

**Accessibility floor is a hard minimum, not an enhancement pass:** 4.5:1 text contrast (use `--ink`/`--ink-2` per UI-UX §9, never `--silt` for anything a decision depends on), focus rings always visible (2px `--indus`, 2px offset, never `outline: none` without a replacement), full keyboard path (Tab/Enter/arrows/Esc/`A` for Acknowledge), `aria-label` on every pin and badge naming urgency + district + verification state in words, live-region announcements throttled to one per 3 seconds plus a count, 32px minimum target size (44px touch), and the layout must hold at 200% browser zoom with no horizontal scroll.

**No build step.** This directory is vanilla JS + Leaflet + Tailwind/fonts from CDN, loaded straight from `index.html` with no bundler. Don't add a package.json with a build script, a framework, or a transpile step — it must still open from `file://` if the venue network dies.

## Before adding any new component

Check UI-UX §6 for whether it already has a spec (filter chip, ticket card, arrival animation, map, table/drawer, audio player/waveform, status badge, button, toast). If it's in there, match it exactly — don't reinterpret. If it genuinely isn't covered, keep it consistent with the tokens and motion rules above rather than introducing a new visual language.
