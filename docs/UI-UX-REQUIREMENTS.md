# UI/UX Requirements

**Project:** Nidaa-AI (Automated Multi-Modal Crisis Triage Engine)
**Version:** 1.0.0 (companion to PRD v4.0.0 and TRD v1.0.0)
**Surface:** Dispatcher command dashboard, desktop first, light theme
**Design direction name:** *Silt and Signal*

---

## 0. The one rule that governs everything below

The dispatcher is a tired human at 3am deciding who gets a boat first. Every effect in this document is allowed to live on the **chrome** (panels, rails, headers, transitions between states) and is forbidden from living **between the dispatcher and the data**. Glass goes behind floating controls, never behind a transcript. Motion carries state changes, never decorates them. If a choice makes the screen prettier and the district name harder to read, the district name wins.

Everything else here is designed to be as beautiful as that constraint allows, which turns out to be very beautiful.

---

## 1. Design Direction

### 1.1 Where the look comes from
Nidaa (ندا) means *the call*. The product listens to the Indus flood plain and answers it. So the visual world is drawn from that basin rather than from generic emergency-red dashboard language:

* **Mist and silt.** The base surfaces are cool river light, a pale blue-grey rather than the warm cream that every AI-generated dashboard defaults to. Silt greys carry the secondary information.
* **Deep Indus teal** is the voice of the system itself: every interactive element, every brand moment.
* **Marigold**, the flower that shows up at every South Asian threshold, doorway and shrine, is the attention colour. It is the colour of "listen to this one yourself."
* **Waveforms**, not gradients, are the decorative language. Sound is what this product actually handles, so sound is what it looks like.

### 1.2 The signature element: the Confidence Waveform
This is the one thing the interface should be remembered for, and it does real work.

Every audio ticket renders a small waveform strip drawn from the actual voice note. The waveform is not decorative: **its rendering encodes Whisper's per-segment confidence.**

* Segments where `avg_logprob` was strong draw as **solid teal bars at full opacity**.
* Segments where confidence dipped draw as **shorter, lower-opacity bars with a 2px dotted baseline underneath**.
* Segments that failed the gate entirely draw as a **flat marigold dotted line**, no bars at all, with the label `could not hear` set in mono directly beneath.

The dispatcher can therefore see, at a glance and without reading a number, *where in the recording the machine stopped understanding*. It turns the most abstract part of the system into something physical. It is also the single most demo-able frame in the product: play the audio and a teal playhead sweeps the strip, going quiet exactly where the bars go dotted.

Text-only tickets get no waveform. They get a left border in the intent colour and slightly more transcript space. The absence is information too.

### 1.3 The second moment: the Time-to-Triage arc
The north star metric does not get a big number with a gradient. It gets a **thin 3px arc**, 120 degrees wide, sitting in the header. The arc fills teal from left to right as the median TTT is plotted against the human baseline at the far left and the 5.0s target at the far right. The current median sits as a small marigold dot on the arc, and it **slides** whenever a new ticket lands. Below it, in mono, the raw figures.

A number tells a judge the system is fast. An arc that visibly sits pinned to the far-fast end of a scale whose other end is labelled `human baseline 3m 20s` tells them how fast, in one glance, with no arithmetic.

---

## 2. Colour

### 2.1 Tokens

| Token | Hex | Role |
| :-- | :-- | :-- |
| `--mist` | `#EBF1F4` | App background, the plane everything floats on |
| `--paper` | `#FCFDFE` | Card and panel surfaces |
| `--paper-sunk` | `#F4F8FA` | Wells, table zebra, input backgrounds |
| `--ink` | `#0A2530` | Primary text, near-black with a teal bias |
| `--ink-2` | `#40606C` | Secondary text, labels, metadata |
| `--silt` | `#8CA3AD` | Tertiary text, disabled, unlocated markers |
| `--line` | `#DCE6EB` | Hairlines, dividers, card borders |
| `--indus` | `#0D6E80` | Primary interactive teal, brand, links, active states |
| `--indus-deep` | `#073B47` | Hover and pressed, display headings |
| `--indus-wash` | `#DFF0F3` | Selected chip fill, active row tint |
| `--vermilion` | `#C62A22` | Critical urgency, disputed state |
| `--vermilion-wash` | `#FBE6E4` | Critical row tint, disputed banner |
| `--marigold` | `#B86E0C` | Attention text, high urgency (text-safe) |
| `--marigold-bright` | `#F5A524` | Attention fills, pins, waveform failure line |
| `--marigold-wash` | `#FDF0DA` | Unintelligible row tint |
| `--reed` | `#1E7A5A` | Confirmed, verified, healthy system state |
| `--reed-wash` | `#DFF2EA` | Confirmed row tint |

Nothing in the palette is a pure grey. Every neutral is mixed toward teal, which is what makes the light theme read as a considered surface rather than a default white page.

### 2.2 Urgency ramp
The urgency scale runs by **temperature, not by rainbow**. It is deliberately only four steps and deliberately not green-to-red, because green would mean "good" and none of these tickets are good.

| Urgency | Fill | Text | Row tint |
| :-- | :-- | :-- | :-- |
| `critical` | `--vermilion` | white | `--vermilion-wash` |
| `high` | `--marigold-bright` | `--ink` | `--marigold-wash` |
| `moderate` | `--indus` | white | `--indus-wash` |
| `info` | `--silt` | `--ink` | none |

### 2.3 State colour is never alone
Colour vision deficiency and a projector with washed-out gamma will both appear on demo day. Every state is encoded **twice**, once in colour and once in shape:

| State | Colour | Shape |
| :-- | :-- | :-- |
| User confirmed | `--reed` | Solid filled pin, small check notch |
| Unconfirmed | urgency colour | Hollow pin, 2px ring, transparent centre |
| User disputed | `--vermilion` | Solid pin with a double outer ring |
| Duplicate cluster | urgency colour | Pin with a numeric badge |
| Audio unintelligible | `--marigold-bright` | No pin. Side rail only, with a struck-through waveform glyph |
| Unlocated | `--silt` | No pin. Side rail only, with a dashed-outline pin glyph |

---

## 3. Typography

### 3.1 Families

| Role | Face | Weights | Why this one |
| :-- | :-- | :-- | :-- |
| UI, Display & Body | **Plus Jakarta Sans** | 400, 500, 600, 700 | Crisp, modern, high-contrast grotesque with geometric clarity and deep legibility across high-density operational screens. |
| Data and numerals | **IBM Plex Mono** | 400, 500 | Timers, P-codes, coordinates, quantities, confidence values. Tabular figures so numbers do not jitter when they update live. |
| Urdu script | **Noto Nastaliq Urdu** / **Gulzar** | 400, 600, 700 | Authentic Nastaliq calligraphy with generous line-height (`2.3+`) for high-fidelity disaster transcripts and SMS readbacks. |

All fonts load from Google Fonts, all free, and easily self-hosted in `fonts/` for pitch demo offline safety.

### 3.2 Scale

| Token | Size / line-height | Tracking | Use |
| :-- | :-- | :-- | :-- |
| `display-xl` | 56 / 56 | -0.03em | The TTT median figure only |
| `display-l` | 34 / 38 | -0.025em | Panel titles |
| `title` | 20 / 26 | -0.015em | Drawer heading, district name in the detail view |
| `body-l` | 16 / 24 | 0 | Transcript body |
| `body` | 14 / 20 | 0 | Default UI text |
| `body-s` | 13 / 18 | 0 | Table cells |
| `caption` | 12 / 16 | 0.01em | Metadata, timestamps |
| `label` | 11 / 12 | 0.09em, uppercase | Eyebrow labels, column headers, status badges |

Rule: uppercase tracked labels appear **only** on things that are genuinely a category or a system state. They never appear on content. This is what stops the interface drifting into decorative-label territory.

### 3.3 Urdu script handling
This is where most teams will visibly fail, so it is specified precisely.

* Raw Urdu-script transcripts render in **Noto Nastaliq Urdu at 18px with `line-height: 2.1`**. Nastaliq is a cascading script and a normal 1.5 line-height clips descenders into the line below. It looks broken and a native reader notices immediately.
* Urdu transcript blocks set `direction: rtl; text-align: right;` on their own container. The surrounding UI stays LTR.
* Roman Urdu is Latin script and stays in Public Sans, LTR. Do not switch fonts for it.
* Mixed code-switched lines use `unicode-bidi: plaintext` so an English word inside an Urdu sentence does not reverse the whole line.
* Never truncate an Urdu line with a CSS ellipsis mid-word. Clamp by line count instead.
* The dispatcher-facing chrome is English. Only sender content and outbound reply previews are Urdu or Roman Urdu.

---

## 4. Shape, Depth and Glass

### 4.1 Radius scale

| Token | Value | Applied to |
| :-- | :-- | :-- |
| `--r-xs` | 4px | Badges, waveform bar caps, tiny tags |
| `--r-s` | 8px | Inputs, small buttons, table row hover highlight |
| `--r-m` | 12px | Buttons, list items, ticket rows |
| `--r-l` | 18px | Cards, floating map panels |
| `--r-xl` | 24px | Detail drawer, modal, the map container itself |
| `--r-full` | 999px | Filter chips, avatars, status dots, the TTT arc caps |

Nested radii follow the standard rule: an inner radius equals the outer radius minus the padding between them, so an 18px card with 8px padding holds 10px children. Concentric corners are the single cheapest thing that makes an interface feel expensive.

### 4.2 Elevation
Shadows are tinted with ink, never with pure black, and always layered in two parts (a tight contact shadow plus a wide ambient one).

```css
--e-1: 0 1px 2px rgba(10,37,48,.06), 0 1px 1px rgba(10,37,48,.04);
--e-2: 0 2px 6px rgba(10,37,48,.07), 0 8px 20px rgba(10,37,48,.05);
--e-3: 0 4px 12px rgba(10,37,48,.08), 0 18px 44px rgba(10,37,48,.08);
--e-glass: 0 2px 8px rgba(10,37,48,.06), 0 20px 50px rgba(7,59,71,.10);
```

### 4.3 Liquid glass, scoped
Glass appears on exactly four surfaces, all of which float over the map. The justification is functional: on a map, an opaque panel destroys spatial context, and a translucent one lets the dispatcher keep seeing the river underneath.

```css
.glass {
  background: rgba(252, 253, 254, 0.72);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  border: 1px solid rgba(220, 230, 235, 0.75);
  box-shadow: var(--e-glass);
  border-radius: var(--r-l);
}
/* the highlight that sells it: a 1px inner light edge along the top */
.glass::before {
  content: ""; position: absolute; inset: 0; border-radius: inherit;
  padding: 1px; pointer-events: none;
  background: linear-gradient(160deg,
    rgba(255,255,255,.85) 0%, rgba(255,255,255,0) 40%);
  -webkit-mask: linear-gradient(#000 0 0) content-box,
                linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
}
```

**Where glass is allowed:** the filter chip bar floating over the map, the map legend card, the map zoom and layer controls, and the toast stack.

**Where glass is banned:** the ticket table, the detail drawer body, any transcript, any input the dispatcher types into, and the TTT header. These carry `--paper` at full opacity.

**Fallback:** wrap in `@supports (backdrop-filter: blur(1px))`. Without support, the same panels render at `rgba(252,253,254,0.96)` with `--e-2`. The layout must never depend on the blur.

### 4.4 Ambient texture
One quiet background treatment, and only one. The `--mist` app background carries a very low contrast contour-line pattern, drawn as a repeating SVG of soft topographic curves at 3% opacity in `--indus`. It reads as river bathymetry at a glance and as nothing at all from two feet away. It is the only decoration in the product. Everything else earns its place by carrying data.

---

## 5. Layout

### 5.1 Desktop shell (1440px reference)

```
┌──────────────────────────────────────────────────────────────────────────┐
│  [◍ nidaa]   TIME TO TRIAGE   ╭───────•──────╮  4.1s median   112 tickets │  72px
│              4.1s p50 · 9.8s p95 · human baseline 3m20s   ● live  q:3     │
├──────────┬───────────────────────────────────────────────┬───────────────┤
│          │  ┌ glass ─────────────────────────────────┐   │               │
│  QUEUES  │  │ ●critical ○high ○moderate │ Dadu ✕ │12h│   │  TICKET       │
│          │  └────────────────────────────────────────┘   │  STREAM       │
│ ▸ All 112│                                               │               │
│ ▸ Critic.│              L E A F L E T   M A P            │ ┌───────────┐ │
│ ▸ Unloc 7│                     ◉  ◎                       │ │▂▅▇▃▁ Dadu│ │
│ ▸ Unhear5│                  ◉     ◉                       │ │ critical  │ │
│ ▸ Disput2│                        ◎                       │ └───────────┘ │
│          │                                               │ ┌───────────┐ │
│  DISTRICT│                              ┌ glass ──────┐  │ │ Sukkur    │ │
│  totals  │                              │  legend     │  │ └───────────┘ │
│          │                              └─────────────┘  │               │
│  [export]│                                               │               │
└──────────┴───────────────────────────────────────────────┴───────────────┘
  260px                    fluid                              420px
```

* **Left rail, 260px, `--paper`.** Queue counts, district aggregate totals, HXL export. Fixed, never scrolls horizontally.
* **Centre, fluid, minimum 560px.** The map is the hero. It fills its column edge to edge with `--r-xl` corners and a 1px `--line` border. Floating glass panels sit inside it with 16px insets.
* **Right rail, 420px, `--paper-sunk`.** The live ticket stream, newest at top. This is where new arrivals animate in.
* **Header, 72px, `--paper`, `--e-1`.** Brand mark, the TTT arc, live indicator, queue depth.

### 5.2 Spacing
4px base unit. Permitted values only: 4, 8, 12, 16, 24, 32, 48, 64. Rail padding 16px. Card padding 16px. Card gap 12px. Section gap 24px.

### 5.3 Density
Ticket rows are 72px tall with the waveform, 56px without. This is deliberately generous. A denser table fits more rows and produces more misclicks, and a misclick here dispatches a boat to the wrong district.

### 5.4 Responsive
* **Below 1180px:** right rail collapses into a bottom sheet with a drag handle, peeked at 120px, expandable to 70vh.
* **Below 860px:** left rail becomes a slide-over triggered from a header button. Filter chips scroll horizontally with a soft mask on both edges.
* **Below 640px:** map and stream become two tabs. Realistically the dispatcher persona is on a desktop, so mobile only needs to be *usable*, not optimised. Build it so a judge on a phone can still open the demo.

---

## 6. Components

### 6.1 Filter chip
The most-touched control in the product and therefore where the interaction polish belongs.

* Rest: `--paper` at 0.72 alpha inside the glass bar, 1px `--line`, `--r-full`, 32px tall, 12px horizontal padding, `body-s` at weight 500, `--ink-2`.
* Hover: border to `--indus` at 40%, text to `--ink`, `transform: translateY(-1px)`, 120ms.
* **Selected:** background `--indus`, text white, and the count badge inverts to a white pill with teal text.
* **The transition:** do not cross-fade the background. Use a shared indicator. A single absolutely positioned teal pill sits behind the chip row and **slides and resizes** to the newly selected chip using a FLIP measurement, 320ms on the `surge` easing. With multi-select, each newly selected chip grows its own pill from the centre outward with a `scaleX` from 0.6 to 1 plus opacity, 240ms, while the label colour cross-fades at 120ms with a 60ms delay so the text never sits illegibly mid-transition.
* Simultaneously, the map runs its filter transition (6.4) and the table runs its stagger (6.5). All three share the same 320ms window so the whole screen moves as one object rather than three.
* Deselect reverses with `settle` easing at 240ms.

### 6.2 Ticket card (right rail)

```
┌────────────────────────────────────────────┐
│ ▎ CRITICAL        09:14:02   4.1s   ⌄      │   ▎ = 3px urgency bar, full height
│                                            │
│  Dadu, Sindh                    PK6...012  │   title / mono pcode
│  20 families need food and water           │   body-s, --ink-2, 2 line clamp
│                                            │
│  ▂▅▇▆▃▁▁ ┈┈┈┈ ▃▅▂                    0:14  │   confidence waveform + duration
│                                            │
│  ○ unconfirmed          [ Acknowledge ]    │   state dot + primary action
└────────────────────────────────────────────┘
```

* `--paper`, `--r-l`, 1px `--line`, `--e-1`. Hover lifts to `--e-2` and `translateY(-2px)` over 160ms.
* The 3px left urgency bar is the only saturated colour in the resting card. Restraint is what makes the critical ones actually pop.
* Whole card is one click target. `Acknowledge` stops propagation.

### 6.3 Arrival animation (the moment judges will watch)
A new ticket landing is the product working. It gets an orchestrated three-part sequence, total 900ms, all of it interruptible.

1. **0ms.** The map pin drops in: `translateY(-14px)` to `0` with `scale(0.7)` to `1`, 420ms `surge`. A single `--indus` ring expands from the pin at `scale(0.3)` to `scale(2.6)` while fading 0.45 to 0, 700ms `ease-out`. One ring only. Two rings is a video game.
2. **120ms.** The ticket card slides into the top of the right rail: height animates from 0 to natural over 300ms while opacity goes 0 to 1 and `translateY(-8px)` to `0`. Cards below shift down with the same 300ms so nothing jumps.
3. **200ms.** The card's background flashes to its urgency wash at 100% and decays back to `--paper` over 1400ms `ease-out`. This is the "arrival glow." It is the one effect in the product that exists partly because it is beautiful, and it is justified because peripheral vision catches a decaying tint far better than it catches a static coloured dot.
4. **In parallel.** The TTT arc dot slides to its new position over 500ms and the header median count rolls with a digit-flip on tabular figures.

If three tickets arrive within 400ms, stagger steps 2 and 3 by 60ms each and suppress the ring on all but the first. A burst should feel like rainfall, not a strobe.

### 6.4 Map
* Tiles: OpenStreetMap standard, plus a cached offline tile set for the Sindh and south Punjab bounding box.
* Tiles are desaturated and lightened with `filter: saturate(0.55) brightness(1.08) contrast(0.94)`. This is essential: raw OSM tiles are colourful enough to compete with the urgency pins, and the pins must be the loudest thing on the map.
* Pins are custom SVG divIcons, not the default Leaflet marker. 28px, with the shape semantics from 2.3.
* **Filter transition:** outgoing pins `scale(1)` to `scale(0.4)` with opacity to 0 over 200ms; incoming pins reverse over 280ms with a 12ms stagger ordered by latitude, so the change sweeps north to south across the province. It costs nothing and it looks like weather.
* Cluster pins carry a count badge and expand into a spiral on click with a 260ms stagger.
* Hovering a ticket card in the right rail makes its pin grow to `scale(1.25)` and drop a soft `--indus` glow, and vice versa. Bidirectional linking is the cheapest way to make a map and a list feel like one instrument.

### 6.5 Ticket table and detail drawer
* Rows: 56px, `body-s`, alternating `--paper` and `--paper-sunk`. Hover fills `--indus-wash` at 40% with `--r-s` inset by 4px, so the highlight looks like a floating pill rather than a full-bleed band.
* **Row to drawer transition:** a shared-element FLIP. On click, the row's bounding box is measured, the drawer mounts at that exact box, and it expands to the right-side drawer position over 380ms `surge` while its internal content cross-fades in with a 120ms delay. The waveform strip is the shared element: it morphs from the 32px card strip to the full 96px drawer waveform in the same motion. The dispatcher never loses track of which ticket they opened, which matters when nine of them say "Dadu."
* Drawer: 520px wide, `--paper`, `--r-xl` on the left corners only, `--e-3`, full height with 24px padding. A `--mist` scrim at 24% alpha covers the rest, with a 200ms fade.
* Drawer contents, in this order, because this is the order of trust: raw audio player with the full Confidence Waveform, then the transcript (Nastaliq or Latin as appropriate), then the extracted fields as a definition list, then the confidence bar and geocode method badge, then the two verdict buttons pinned to the bottom on a hairline-topped bar.
* Close on `Esc`, scrim click, or the close button. Exit reverses the FLIP at 280ms `settle`.

### 6.6 Audio player and waveform
* Play button 40px, `--indus` fill, white triangle, `--r-full`. Pressed state scales to 0.94 over 80ms.
* The waveform playhead is a 2px `--indus-deep` vertical line. Played bars sit at full saturation, unplayed bars at 45% opacity. The line moves with `requestAnimationFrame`, never with a CSS transition, so it stays locked to the audio.
* Clicking anywhere on the waveform seeks. The hit area extends 8px above and below the visible bars.
* `AUDIO_UNINTELLIGIBLE` tickets show the waveform as a flat marigold dotted line with the caption `Nidaa could not hear this. Listen yourself.` set in `label` style. The play button is still present and still works, which is the entire point.

### 6.7 Status badges
`label` type, 20px tall, `--r-full`, 8px horizontal padding, wash background with the matching text colour. Never more than one badge per row. If a ticket is both duplicate and disputed, disputed wins, because that is the one a human needs to touch.

### 6.8 Buttons

| Variant | Fill | Text | Border | Use |
| :-- | :-- | :-- | :-- | :-- |
| Primary | `--indus` | white | none | Acknowledge, Export |
| Danger-quiet | `--vermilion-wash` | `--vermilion` | 1px `--vermilion` at 25% | Flag as wrong |
| Ghost | transparent | `--ink-2` | 1px `--line` | Close, secondary |

36px tall, `--r-m`, `body-s` weight 600. Hover darkens 8% and lifts 1px over 120ms. Press scales to 0.98 over 60ms. Focus ring is a 2px `--indus` outline at 2px offset, always visible on keyboard focus, never removed.

### 6.9 Toast
Glass, bottom right, stacked with 8px gaps, 4.5s auto-dismiss with a hairline progress line in `--indus` draining along the bottom edge. Enters with `translateX(16px)` and opacity over 260ms. Used for: verdict recorded, export downloaded, WhatsApp session lost, sender replied to a readback.

---

## 7. Motion System

### 7.1 Easings

```css
--surge:  cubic-bezier(0.22, 1.00, 0.36, 1.00);  /* entrances, expansion */
--settle: cubic-bezier(0.40, 0.00, 0.20, 1.00);  /* exits, dismissals */
--snap:   cubic-bezier(0.30, 0.00, 0.10, 1.00);  /* small state flips */
```

`--surge` is the house curve. It decelerates hard at the end, which is what makes a panel feel like it has weight and settles rather than stops.

### 7.2 Durations

| Interaction | Duration |
| :-- | :-- |
| Colour or opacity on a small control | 120ms |
| Hover lift, press | 120 / 60ms |
| Chip selection indicator slide | 320ms |
| Map pin filter in / out | 280 / 200ms |
| Row to drawer FLIP | 380ms |
| Drawer close | 280ms |
| Arrival glow decay | 1400ms |
| Metric roll | 500ms |

Nothing exceeds 400ms except decays that the dispatcher never has to wait on. Nothing below 60ms, because that reads as a glitch rather than a response.

### 7.3 Reduced motion
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    transition-duration: .01ms !important;
  }
}
```
With one exception, applied explicitly: the arrival glow keeps a 300ms opacity fade rather than snapping, because a hard flash is worse for motion-sensitive users than a soft one. Ring pulses, pin drops and staggers are removed entirely and replaced with instant state changes.

---

## 8. States, Empty and Error

Errors state what happened and what to do. They do not apologise and they are never vague.

| Situation | Display |
| :-- | :-- |
| No tickets yet | Centred, a 64px outlined waveform glyph in `--silt`, then `Listening.` in `display-l`, then `Messages sent to the triage number will appear here within seconds.` in `body`, `--ink-2`. |
| Filters return nothing | `No tickets match these filters.` plus a `Clear filters` ghost button. Never an illustration. The dispatcher caused this state and knows it. |
| WhatsApp session lost | Persistent 40px header bar in `--marigold-wash` with `--marigold` text: `WhatsApp ingestion disconnected. Reconnecting. Processing continues for messages already received.` |
| Rate limited | Queue depth number in the header turns `--marigold` and gains the tooltip `Holding messages to stay inside the free API limit. Nothing is dropped.` |
| Geocode failed | The ticket sits in the Unlocated queue with `No location stated. Live location requested from sender.` |
| Extraction failed | `Nidaa could not structure this message. Read the transcript and triage manually.` with the transcript already expanded. |

Voice notes: sentence case, plain verbs, the system refers to itself as Nidaa, never as "we" and never as "I." Buttons keep their name through the whole flow, so `Acknowledge` produces the toast `Acknowledged`.

---

## 9. Accessibility Floor

* Body text meets 4.5:1 against its background. `--ink` on `--paper` clears 15:1. `--ink-2` on `--paper` clears 7:1. `--silt` is used only for non-essential text at 13px or larger, and never for anything a decision depends on.
* Focus is always visible: 2px `--indus` outline, 2px offset. Never `outline: none` without a replacement.
* Full keyboard path: `Tab` through chips, `Enter` toggles, arrow keys move through the ticket list, `Enter` opens the drawer, `Esc` closes, `A` acknowledges the focused ticket.
* Every pin and badge carries an `aria-label` naming urgency, district and verification state in words.
* Live regions: new tickets announce as `Critical ticket, Dadu, food and water for 20 families` via `aria-live="polite"`. Bursts are throttled to one announcement per 3 seconds plus a count.
* Target sizes are 32px minimum, 44px on touch.
* The interface works at 200% browser zoom without horizontal scrolling.

---

## 10. Demo Presentation Notes

* Build a `?present=true` flag that increases all type by 12% and thickens hairlines to 1.5px. Projectors eat thin lines and 13px text.
* The header live dot pulses at 2s intervals in `--reed`. It is the only ambient animation on the page, and it tells a judge across the room that the thing is alive.
* Pre-load and cache the map tiles for the demo bounding box before you walk on stage.
* Have the drawer open on a `AUDIO_UNINTELLIGIBLE` ticket as the resting frame if the demo stalls. That single screen contains the whole thesis: a flat marigold dotted line, the words `Nidaa could not hear this. Listen yourself.`, and the outgoing Roman Urdu message asking the sender to type instead.

---

## 11. Logo

### 11.1 The concept
The Urdu letter **nūn (ن)** opens the word ندا. It is a shallow bowl with a single dot floating above it. That form is already three things at once:

* a **bowl**, which reads as a boat hull, and boats are how people are pulled out of the Indus,
* a **cradle for sound**, which is what a waveform envelope looks like,
* and the **dot**, which is exactly a map pin's point.

The mark is that letter, geometrically rebuilt: a confident bowl stroke whose interior is subtly waveform-notched, with the dot lifted above it as a filled marigold pin dot. It is legible to an Urdu reader as ن, and legible to everyone else as a signal above a curve.

### 11.2 Specifications
* Primary lockup: mark to the left, wordmark `nidaa` in Archivo Expanded 700 lowercase, `.ai` in `--silt` at the same size. Gap between mark and wordmark equals the cap height.
* Mark colours: bowl in `--indus-deep` `#073B47`, dot in `--marigold-bright` `#F5A524`.
* One-colour version: everything in `--indus-deep`, dot retained, no gradient.
* Clear space: half the mark's height on all four sides.
* Minimum size: 20px tall for the mark alone, 96px wide for the full lockup.
* App icon: mark centred on `--paper` with a `--r-xl` squircle and a very faint teal contour texture at 4%.
* Never: gradient the bowl, add a drop shadow, rotate the mark, place the mark on a photograph, or separate the dot from the bowl.

### 11.3 Generation prompts

**Primary mark**
```
Minimal flat vector logo mark. A single thick confident curved
stroke forming a shallow open bowl, like the Urdu letter noon or a
boat hull viewed from the side. The inner edge of the bowl is
subtly notched into a small symmetrical sound-waveform pattern,
five short bars, barely visible, integrated into the stroke itself.
A single perfectly round solid dot floats centred above the bowl,
positioned like the point of a map pin. Deep teal stroke #073B47,
marigold dot #F5A524, flat white background. Geometric, precise,
even stroke weight, rounded stroke caps. No gradient, no shadow,
no 3D, no text, no outline box. Humanitarian technology brand
identity, clean vector, generous negative space.
```

**Wordmark lockup**
```
Horizontal logo lockup on white. Left: a minimal deep teal curved
bowl mark with a single round marigold dot floating above it.
Right: the lowercase wordmark "nidaa.ai" in a wide extended
geometric sans serif, heavy weight, tight letter spacing, deep
teal, with the ".ai" suffix in a lighter cool grey. Baseline of
the wordmark aligns with the base of the bowl. Flat vector,
crisp edges, no effects, generous clear space, professional
humanitarian technology branding.
```

**App icon**
```
App icon, rounded square with a soft 24px corner radius, very pale
cool blue-grey background #EBF1F4 with an almost invisible
topographic contour line texture at 3 percent opacity. Centred: a
deep teal #073B47 curved bowl stroke with a solid marigold #F5A524
round dot floating above it. Flat vector, no gradient, no shadow
on the mark, generous padding around the symbol, iOS style icon
composition.
```

**Alternate direction, if the letterform reads too abstract**
```
Minimal flat vector logo mark. A teardrop map pin shape drawn as a
single deep teal outline, hollow inside. Inside the hollow, a small
symmetrical audio waveform of five vertical bars, the centre bar
tallest, in solid marigold. Balanced, geometric, even stroke
weight. Flat white background, no gradient, no shadow, no text.
Crisp vector, humanitarian emergency response branding.
```

**Negative prompt for any of the above**
```
No gradients, no drop shadows, no 3D bevel, no glossy highlight,
no photorealism, no globe, no red cross, no megaphone, no generic
speech bubble, no swoosh, no water splash clipart, no stock icon
look, no text unless requested, no busy detail, no soft focus.
```

### 11.4 A note on the mark
Ask a native Urdu reader on your team to confirm the bowl reads as nūn before you commit. A letterform that is nearly right is worse than an abstract shape, and this is a track judged partly on whether the language work is genuine.
