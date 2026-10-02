# Data

This folder holds **lists only**. The repository contains no video, no picture and no
index. The scripts write their outputs into this folder too (`shots/`, `keyframes/`,
`frames/`, `index/` ...), and git ignores them.

## videos.csv

The 873 videos this system was developed on; the code in this repository was tested end
to end on a few of them, landscape and portrait. They are the videos the organisers of the
HCM AI Challenge 2026 released for the qualifying round. The organisers' own keyframe maps for
them are labelled as belonging to the first batch of the 2025 challenge's collection. Each was
first published on YouTube.
The list points at YouTube, the original source, rather than at download links, which expire.
On 2 October 2026, 849 of the 873 links opened through YouTube's oEmbed endpoint. The other 24, every
video of group L28 (`L28_V001` to `L28_V024`), answered 403 and their watch pages say the video is
private, so the list keeps their metadata but you can no longer open them there.

| Column | Meaning |
|---|---|
| `video_id` | the organisers' name for the video, `L<group>_V<number>`; the scripts expect the file `<video_id>.mp4` |
| `youtube_id`, `url` | the video on YouTube |
| `title`, `channel`, `published` | as recorded in the YouTube metadata the organisers distributed |
| `length_s` | length in seconds, as YouTube reports it |
| `fps`, `frames` | frame rate and number of decoded frames of the organisers' copy (decoded with PyAV) |
| `width`, `height` | picture size of the organisers' copy |

```text
video_id,youtube_id,url,title,channel,published,length_s,fps,frames,width,height
L21_V001,Rzpw5WR7nAY,https://www.youtube.com/watch?v=Rzpw5WR7nAY,60 Giây Sáng - Ngày 01082024 - HTV Tin Tức Mới Nhất 2024,60 Giây Official,2024-08-01,1262,30,37849,1280,720
```

| Channel | Content | Videos | Hours |
|---|---|---:|---:|
| ViVU TV | cooking | 498 | 43.8 |
| Báo Thanh Niên | exam lessons for the national high-school exam | 88 | 36.2 |
| 60 Giây Official | news bulletins | 60 | 19.1 |
| HTV Entertainment, HTV Giải Trí | travel | 63 | 17.0 |
| HTV Sports | cycling race, lion and dragon dance | 68 | 8.9 |
| Báo Tuổi Trẻ | short features | 96 | 5.7 |

| | |
|---|---|
| videos | 873, groups L21 to L30 |
| length | 130.7 hours, 12,258,989 frames |
| published | April 2020 to October 2024 |
| frame rate | 25 fps: 781 videos; 30 fps: 61; 30000/1001 fps: 30; 13219/500 fps: 1 |
| picture | 1280×720: 869 videos; 720×1280 (portrait): 4 |

For every video, the organisers' copy is as long as the YouTube video, give or take a
second (the largest difference is 0.6 s).

## Frame numbers depend on the exact file

Answers are frame numbers, and times, in the organisers' copies. A copy of a video from
anywhere else may have a different frame rate or a different number of frames. Then every
frame number computed from it is shifted, and a correct-looking answer is wrong. Before
you trust a copy, compare its `fps` and `frames` with the list:

```bash
ffprobe -v error -select_streams v:0 -count_frames \
        -show_entries stream=avg_frame_rate,nb_read_frames -of csv=p=0 L30_V031.mp4
# 25/1,3499   -> matches the list
```

`scripts/preprocess.py` checks the frame count of every video in this list, and prints a
warning when it differs.

## Using the videos

Put the files, named `<video_id>.mp4`, in one folder (subfolders are fine), then run
`python scripts/preprocess.py --videos that/folder`. Videos that are not in the list work
too; they are simply not checked.

The videos belong to their broadcasters and are not redistributed here. Use them under the
terms of the organisers and of YouTube.

## Not used

The organisers also distribute keyframes, keyframe maps, CLIP features and object
detections for these videos. This system rebuilds everything it needs from the videos
themselves ([docs/offline/](../docs/offline/README.md)) and uses none of those files.
