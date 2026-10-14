/**
 * The few small pictures the controls use, drawn here as outlines (16 x 16, one stroke width), so the
 * page needs no icon font or image file. They take the colour of the text around them.
 */
const PATHS = {
  add: '<path d="M8 3v10M3 8h10"/>',
  play: '<path d="M5.5 3.5v9l7-4.5z"/>',
  similar: '<rect x="2" y="5" width="8" height="8" rx="1.5"/><path d="M6 2.5h6.5A1.5 1.5 0 0 1 14 4v6.5"/>',
  film: '<rect x="2" y="3" width="12" height="10" rx="1.5"/><path d="M5.5 3v10M10.5 3v10M2 6.5h3.5M2 9.5h3.5M10.5 6.5H14M10.5 9.5H14"/>',
  external: '<path d="M9 2.5h4.5V7M13.5 2.5 7.5 8.5M12 9.5V12a1.5 1.5 0 0 1-1.5 1.5H4A1.5 1.5 0 0 1 2.5 12V5.5A1.5 1.5 0 0 1 4 4h2.5"/>',
  close: '<path d="M4 4l8 8M12 4l-8 8"/>',
  up: '<path d="M4 9.5 8 5.5l4 4"/>',
  down: '<path d="M4 6.5l4 4 4-4"/>',
  remove: '<path d="M4 4l8 8M12 4l-8 8"/>',
  download: '<path d="M8 2.5v7.5M4.5 7 8 10.5 11.5 7M3 13h10"/>',
  trash: '<path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5"/>',
  branch: '<circle cx="4.5" cy="3.5" r="1.5"/><circle cx="4.5" cy="12.5" r="1.5"/><circle cx="11.5" cy="5.5" r="1.5"/><path d="M4.5 5v6M11.5 7c0 2.5-2.2 3.2-7 3.8"/>',
  record: '<circle cx="8" cy="8" r="5.5"/><circle cx="8" cy="8" r="1.8"/>',
  arrow: '<path d="M3 8h10M9 4l4 4-4 4"/>',
  search: '<circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5 14 14"/>',
};

/** A decorative icon: hidden from screen readers, because the control that holds it has its own name. */
export function icon(name) {
  const span = document.createElement('span');
  span.className = 'icon';
  span.setAttribute('aria-hidden', 'true');
  span.innerHTML = `<svg viewBox="0 0 16 16" width="16" height="16" fill="none" stroke="currentColor" `
    + `stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">${PATHS[name]}</svg>`;
  return span;
}
