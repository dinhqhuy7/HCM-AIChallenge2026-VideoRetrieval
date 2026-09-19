/** The competition's submission file: one CSV line per answer, no header. */
export class CsvExporter {
  static text(answers) {
    return answers.map((answer) => `${answer.cells().map(quote).join(',')}\n`).join('');
  }

  static download(fileName, answers) {
    const url = URL.createObjectURL(new Blob([CsvExporter.text(answers)], { type: 'text/csv' }));
    Object.assign(document.createElement('a'), { href: url, download: fileName }).click();
    // Revoked a moment later: some browsers still read the URL after click() returns.
    setTimeout(() => URL.revokeObjectURL(url));
  }
}

/** Free-text answers may hold commas or quotes; such cells are quoted per RFC 4180. */
const quote = (value) => {
  const cell = String(value);
  return /[",\r\n]/.test(cell) ? `"${cell.replaceAll('"', '""')}"` : cell;
};
