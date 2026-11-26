# Frontend design rules

> **Visual system: [`.claude/design/DESIGN-spotify.md`](../design/DESIGN-spotify.md)** (D-015). It wins over any visual rule below (dark theme, green accent, pill buttons, heavy shadows on dark). The rules below still bind for UX, forms, accessibility, and responsiveness. Use the system's look, not Spotify's brand: no Spotify name, logo, or proprietary fonts.
## Design principles
- Aim for a clean, modern UI
- Minimize unnecessary decoration
- Content readability first
- Consider both mobile and desktop
- Apply responsive design

## Page design
### Consistency
- Every page uses the same design system
- The same color palette
- The same button style
- The same card style
- The same input form style
- The same spacing rules

### Reference design
- `DESIGN-spotify.md`: dark, content-first, dense app UI

## Color rules
### Primary color
- One brand color
- Used for primary buttons, links, and emphasis

### Secondary color
- 1–2 secondary colors
- Used for status and emphasis

### Neutral color
- Near-black/charcoal surfaces (`#121212`–`#272727`) and white/silver text
- Pure black (#000000) only for icons on the green accent

### Principles
- No excessive colors on one screen
- No meaningless gradients
- Never convey information by color alone

## Layout rules
### Content width
- Set a maximum content width
- No overly wide layouts

### Spacing
- Use a consistent spacing scale
- Keep spacing between components consistent

### Alignment
- Left alignment first
- Center alignment only for specific purposes such as landing pages

## Card design
- Rounded corners
- Shadows per DESIGN-spotify.md §6 (heavy shadows are needed on dark)
- Provide a hover state
- Consistent inner padding

## Button design
### Primary button
- Only for the most important action

### Secondary button
- For secondary actions

### Common rules
- Make the clickable state clear
- Provide a hover state
- Provide a disabled state

## Form design
- Labels are required
- Never rely on placeholders alone
- Provide validation messages
- Give clear visual feedback in error states

## Typography
### Headings
- A clear hierarchy
- Follow H1 → H2 → H3 order

### Body
- A readable size
- No oversized fonts

### Fonts
- One font across the project
- At most 2 font families

## Icons
- One icon library
- No meaningless icons
- Use icons to support text, not replace it

## Responsive design
### Mobile first
- Design for mobile screens first

### Supported range
- Mobile
- Tablet
- Desktop

### Rules
- No horizontal scrolling
- Change the layout appropriately by screen size

## Accessibility
- Keyboard navigable
- Enough color contrast
- Alt text for images
- Buttons and links must be distinguishable

## Don't
- Excessive animation
- Excessive gradients
- Mixing several design styles on one page
- Meaningless colors
