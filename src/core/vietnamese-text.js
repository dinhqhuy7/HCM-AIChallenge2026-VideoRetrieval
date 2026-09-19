/** Folds Vietnamese text to unaccented lowercase words, so "bao lu" finds "bão lũ". */
export class VietnameseText {
  static fold(text) {
    return text.toLowerCase().normalize('NFD').replace(/đ/g, 'd').replace(/\p{M}/gu, '');
  }

  static words(text) {
    return VietnameseText.fold(text).split(/[^a-z0-9]+/).filter(Boolean);
  }
}
