/** 83.4 seconds -> "1:23". */
export function clock(seconds) {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, '0')}`;
}

/** Two moments as one range: 12 and 15.2 -> "0:12–0:15"; when both read the same, just "0:12". */
export const span = (from, to) => (clock(from) === clock(to) ? clock(from) : `${clock(from)}–${clock(to)}`);
