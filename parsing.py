import csv
from math import ceil, floor

from annotation import Annotation


def parse_video_fps_file(video_frames_info_path):
    """Parse video frame info file.

    Each line should be of the form "<video_name>,<fps>[,<any_other_fields>]

    Returns:
        video_fps (dict): Maps filename to fps.
    """
    video_fps = dict()
    with open(video_frames_info_path) as f:
        reader = csv.reader(f)
        next(reader, None)  # Skip headers
        for row in reader:
            video_fps[row[0]] = float(row[1])
    return video_fps


def parse_annotation_file(annotation_path, video_fps, category):
    annotations = []
    with open(annotation_path) as f:
        for line in f:
            # Format: "<video_name> <start_time> <end_time>" or
            # "<video_name>  <start_time> <end_time>".
            # The THUMOS temporal labels have *two spaces* between the first two
            # fields (unfortunately), while the MultiTHUMOS labels have one
            # space.
            details = line.strip().split(' ')
            if details[1] == '':  # There were two spaces after the first field.
                details.pop(1)
            filename, start, end = details
            start, end = float(start), float(end)
            current_fps = video_fps[filename]
            start_frame = floor(start * current_fps)
            end_frame = ceil(end * current_fps)
            annotations.append(Annotation(**{'filename': filename,
                                             'start_seconds': start,
                                             'end_seconds': end,
                                             'start_frame': start_frame,
                                             'end_frame': end_frame,
                                             'frames_per_second': current_fps,
                                             'category': category}))
    return annotations