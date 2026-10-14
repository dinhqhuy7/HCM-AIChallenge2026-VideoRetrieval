/**
 * What the main branch's own guides show of its output, copied here so the "How it works" page can
 * put it beside recorded data. Nothing in this file was produced by this page: each entry names the
 * guide (under `docs/` of the main branch) it is copied from, and the video it is about is the
 * 65-second L30_V040 that those guides use as their example.
 */
export const MAIN = {
  /** `offline/README.md`, "Shots" and "The keyframe map": shot 1 of the video and its keyframe (the line is shortened). */
  shot: {
    guide: 'offline/README.md',
    lines: [
      '{"video_id": "L30_V040", "shot_id": 1, "start_frame": 75, "end_frame": 169, "start_ms": 3000, "end_ms": 6800}',
      '{"video_id": "L30_V040", "keyframe_id": "L30_V040_000122", "shot_id": 1, "frame_index": 122, "time_ms": 4880, …}',
    ],
  },

  /** `offline/03-ocr.md`, "Output": five of the lines read on keyframe 122, a title card that says "thương hiệu quản lý cân nặng". */
  ocr: {
    guide: 'offline/03-ocr.md',
    keyframe: 'L30_V040_000122',
    lines: ['Herbalife', 'thương hiu', 'quán ly', '#', 'cân nng'],
  },

  /** `offline/04-asr.md`, "Output": the first segments of the same video. */
  asr: {
    guide: 'offline/04-asr.md',
    lines: [
      '{"start_ms": 540, "end_ms": 19140, "text": "Được thành lập từ tháng 4 năm 2019 bởi một cặp đôi 9X,"}',
      '{"start_ms": 19520, "end_ms": 23420, "text": "vườn mèo lang thang đã trở thành mái âm chung của những chú mèo bị bỏ rơi và bạo hành."}',
      '{"start_ms": 24160, "end_ms": 28380, "text": "Trạm cứu hộ này đã giải cứu mèo ở hầu hết các quận, huyện trên địa bàn TP.HCM,"}',
    ],
  },

  /**
   * `online.md`, "Fusion": on the guide's test index, `--text "a title card with a logo" --ocr herbalife`
   * put the card first where the visual box alone had put it fifth. The OCR box returned that one shot.
   * `k` is the value of the paper that introduced the fusion; the guide leaves it for you to set.
   */
  fusion: {
    guide: 'online.md',
    k: 60,
    query: '--text "a title card with a logo" --ocr herbalife',
    visual: { card: 5, others: [1, 2, 3] },
    ocr: { card: 1 },
  },

  /** `submission.md`, "CSV files": the row of each task. */
  rows: [
    { task: 'KIS', row: 'video_id,frame_id', example: 'L23_V005,2428' },
    { task: 'Q&A', row: 'video_id,frame_id,answer', example: 'L23_V005,2428,hai người' },
    { task: 'TRAKE', row: 'video_id,frame_id_1,…,frame_id_n', example: 'L23_V005,2428,3185,3658' },
  ],
};
