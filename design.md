---
version: alpha
name: Design Extractor
description: Minimal monochrome landing page system with heavy typographic contrast and soft neutral surfaces.
colors:
  primary: "#171717"
  secondary: "#525252"
  tertiary: "#e5e5e5"
  neutral: "#ffffff"
  surface: "#fbfbfb"
  on-surface: "#171717"
  error: "#b91c1c"
  border: "#e5e7eb"
typography:
  headline-display:
    fontFamily: Inter
    fontSize: 80px
    fontWeight: 700
    lineHeight: 96px
    letterSpacing: -4px
  headline-lg:
    fontFamily: Inter
    fontSize: 57px
    fontWeight: 700
    lineHeight: 68px
    letterSpacing: -1.28px
  headline-md:
    fontFamily: Inter
    fontSize: 40px
    fontWeight: 600
    lineHeight: 48px
    letterSpacing: -0.32px
  headline-sm:
    fontFamily: Inter
    fontSize: 28px
    fontWeight: 600
    lineHeight: 34px
    letterSpacing: 0px
  body-lg:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: 400
    lineHeight: 30px
    letterSpacing: -0.4px
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: 400
    lineHeight: 24px
    letterSpacing: -0.2px
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 20px
    letterSpacing: 0px
  label-lg:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 500
    lineHeight: 18px
    letterSpacing: 0px
  label-md:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 400
    lineHeight: 18px
    letterSpacing: 0px
  label-sm:
    fontFamily: Geist Mono
    fontSize: 12px
    fontWeight: 500
    lineHeight: 16px
    letterSpacing: 0.02em
  code-sm:
    fontFamily: Geist Mono
    fontSize: 12px
    fontWeight: 400
    lineHeight: 16px
    letterSpacing: 0px
  eyebrow:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 500
    lineHeight: 16px
    letterSpacing: 0.04em
  metric-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: 600
    lineHeight: 24px
    letterSpacing: 0px
rounded:
  none: 0px
  sm: 4px
  md: 8px
  lg: 12px
  xl: 24px
  full: 9999px
spacing:
  xs: 6px
  sm: 14px
  md: 24px
  lg: 40px
  xl: 48px
  gutter: 24px
  section: 80px
components:
  button-primary:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.secondary}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.full}"
    padding: 8px 16px
    height: 38px
  button-primary-hover:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.primary}"
    rounded: "{rounded.full}"
  button-secondary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral}"
    typography: "{typography.label-lg}"
    rounded: "{rounded.full}"
    padding: 8px 16px
    height: 38px
  button-tertiary:
    backgroundColor: "transparent"
    textColor: "{colors.secondary}"
    typography: "{typography.label-md}"
    rounded: "{rounded.none}"
    padding: 0px
  card:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.md}"
    padding: 16px
  input:
    backgroundColor: "{colors.neutral}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.full}"
    padding: 16px 20px
    height: 60px
  chip:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.secondary}"
    rounded: "{rounded.full}"
    padding: 8px 12px
  chip-active:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.neutral}"
    rounded: "{rounded.full}"
    padding: 8px 12px
---

# Design Extractor

## Overview
Design Extractor feels crisp, minimal, and product-led, with a strong “build for builders” tone. It uses a mostly white canvas, compact controls, and oversized headlines to communicate confidence without visual clutter. The audience appears to be technical users—especially AI and web tooling users—so the system favors clarity, speed, and low-friction actions over ornamental detail.

## Colors
- **Primary (#171717):** The core ink color used for the biggest headlines, filled buttons, and the strongest contrast moments. It reads as near-black rather than pure black, keeping the interface soft but authoritative.
- **Secondary (#525252):** A muted gray for supporting text, navigation links, helper copy, and low-emphasis button labels. It keeps the hierarchy calm and readable.
- **Tertiary (#e5e5e5):** A light neutral border tone used for dividers, pills, and subtle outlines. It creates structure without adding visual weight.
- **Neutral (#ffffff):** The main background and surface base. The page relies on white space as a primary design material.
- **Surface (#fbfbfb):** A barely-tinted surface for light button treatments and passive UI elements. It helps separate controls from the pure white canvas.
- **On-surface (#171717):** Primary text placed on white or pale surfaces. Use for high-legibility content and bold utility UI.
- **Border (#e5e7eb):** Slightly cooler edge color for cards and framed content. This is especially useful where a softer border is needed than the generic tertiary line.
- **Error (#b91c1c):** Reserved for destructive or validation states. It is not prominent in the screenshot, but should remain restrained and highly specific.

## Typography
Inter is the dominant family for nearly all interface text, giving the system a modern, compact, and highly legible character. Headlines are aggressively bold and tightly tracked, with the display scale using large negative letter spacing to create a dense, editorial feel. Body copy remains lighter and more relaxed, while labels and utility text stay small and efficient for interface chrome.

Use `headline-display` and `headline-lg` for landing-page hero messaging, `headline-md` for section titles, and `headline-sm` for smaller subheads. `body-lg` supports marketing explanation text, while `body-md` and `body-sm` handle helper text, nav items, and secondary UI. `label-lg` and `label-md` are appropriate for buttons, pills, and form affordances.

Uppercase styling is not a defining pattern here; emphasis comes from weight, size, and spacing rather than forced caps. For compact technical annotations or credit-like text, `Geist Mono` can be used through `label-sm` or `code-sm` to echo the tool-oriented personality.

## Layout
The layout is centered and modular, with a wide desktop canvas and a strong vertical hero stack. Large whitespace surrounds the primary content, while lower sections shift into card-based groupings that feel like featured content previews. The system should favor a fixed centered container with generous side margins rather than a dense full-bleed grid.

Spacing follows a clear, restrained rhythm: `xs` for tiny gaps, `sm` for inline label separation, `md` for standard component spacing, and `lg`/`xl` for sectional breathing room. Use `section` for major vertical breaks and keep card interiors close to `16px` padding to preserve the lightweight feel. Controls and badges should remain compact, with only a few points of padding variation between states.

## Elevation & Depth
The interface is intentionally flat, with almost no shadow-driven depth. Hierarchy is communicated through typography scale, spacing, and thin borders rather than heavy elevation. Where depth is needed, use subtle 1px strokes and pale surfaces instead of drop shadows.

Cards and controls should feel clean and slightly inset from the page via borders and soft neutral fills. Avoid pronounced blur, colored shadows, or layered elevation stacks. The visual language should stay crisp and browser-native, with depth implied by contrast and containment.

## Shapes
The shape language is soft and pill-heavy. Primary buttons, inputs, and chips use full rounding to create approachable, friendly controls that contrast with the bold typography. Cards use a smaller `md` radius for a more grounded rectangular frame.

Overall, the system feels rounded but not playful. Rounded corners are used for tactility and polish, while large display text keeps the brand serious and technical. Avoid sharp corners on interactive elements unless you are intentionally making a tertiary link-like control.

## Components
**Buttons:** Primary and secondary buttons are compact pills around 38px tall with `8px 16px` padding. `button-primary` should stay light with a subtle border and muted text, matching the nav-style CTA treatment, while `button-secondary` is the inverse dark filled action. Hover states should slightly adjust tonal contrast but remain minimal; no dramatic glow or shadow changes. `button-tertiary` is text-only, underlined when used as a link, and should be visually quiet.

**Cards:** Use the `card` token for featured content, previews, and content tiles. Cards should be white, bordered, and lightly padded, with `rounded.md` corners and no shadow. Keep imagery large and edge-to-edge inside the card when appropriate, but preserve a thin border frame for structure.

**Inputs:** The main URL field is the most important form element and should feel like a wide pill with high legibility and minimal chrome. Use a neutral background, soft border, and generous horizontal padding. Keep placeholder text muted and let the submit affordance live as a compact circular control at the right edge.

**Chips and pills:** Use `chip` and `chip-active` for credit selectors, feature tags, and status pills. Inactive chips should be light and bordered; active chips should invert to dark filled treatment. Keep content short and avoid wrapping unless absolutely necessary.

**Navigation:** Top-level navigation is minimal, text-led, and balanced by a compact brand mark. Links should be low-emphasis and restrained, with the right side reserved for sign-in and sign-up actions.

**Cookie/notice bars:** Treat notices as floating rounded banners with a white or pale surface, subtle border, and compact action buttons. They should feel temporary and supportive rather than dominant.

## Do's and Don'ts
- Do keep the interface mostly white with strong black typography and minimal accent color use.
- Do use large, tightly tracked hero text for impact and keep body copy comparatively restrained.
- Do prefer pill-shaped controls for buttons, inputs, and chips.
- Do rely on thin borders and spacing for hierarchy instead of shadows.
- Don't introduce saturated colors, gradients, or decorative illustration styles that compete with the content.
- Don't make buttons bulky or square; the system depends on soft, compact rounding.
- Don't overuse uppercase or condensed labels; the brand reads clearer through weight and alignment.
- Don't add heavy elevation or complex card layering that fights the flat, airy composition.

