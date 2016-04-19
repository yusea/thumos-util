"""Helpers for working with annotations."""
from __future__ import division

import collections
import json

import numpy as np

Annotation = collections.namedtuple(
    'Annotation', ['filename', 'start_frame', 'end_frame', 'start_seconds',
                   'end_seconds', 'frames_per_second', 'category'])


def load_annotations_json(annotations_json_path, filter_category=None):
    """Load annotations into a dictionary mapping filenames to annotations.

    Args:
        annotations_json_path (str): Path to JSON file containing annotations.
        filter_category (str): If specified, only annotations for that category
            are returned.

    Returns:
        annotations (dict): Maps annotation file name to a list of Annotation
            objects.
    """
    with open(annotations_json_path) as f:
        annotations_list = json.load(f)
    annotations = collections.defaultdict(list)
    # Extract annotations for category
    for annotation in annotations_list:
        annotation = Annotation(**annotation)
        annotations[annotation.filename].append(annotation)
    if filter_category is not None:
        annotations = filter_annotations_by_category(annotations,
                                                     filter_category)
        if not annotations:
            raise ValueError('No annotations found with category %s.' %
                             filter_category)
    return annotations


def filter_annotations_by_category(annotations, category):
    """
    Return only annotations that belong to category.

    Args:
        annotations (dict): Maps filenames to list of Annotations.
        category (str): Category to keep annotations from.

    Returns:
        filtered_annotations (dict): Maps filenames to list of Annotations.

    >>> SimpleAnnotation = collections.namedtuple(
    ...         'SimpleAnnotation', ['category'])
    >>> annotations = {'file1': [SimpleAnnotation('class1'),
    ...                          SimpleAnnotation('class2')],
    ...                'file2': [SimpleAnnotation('class2')]}
    >>> filtered = filter_annotations_by_category(annotations, 'class1')
    >>> filtered.keys()
    ['file1']
    >>> len(filtered['file1'])
    1
    """
    filtered_annotations = {}
    for filename, annotations in annotations.items():
        filtered = [x for x in annotations if x.category == category]
        if filtered:
            filtered_annotations[filename] = filtered
    return filtered_annotations


def get_durations(annotations):
    """
    Extract durations from annotations.

    Args:
        annotations (dict): Maps filenames to annotations.

    Returns:
        durations (np.array): List of durations (in frames) for all
            annotations.
    """
    durations = []
    for annotations in annotations.values():
        durations.extend([annotation.end_frame - annotation.start_frame + 1
                          for annotation in annotations])
    return np.asarray(durations)


def compute_min_background_duration(annotations):
    """
    Compute the minimum duration between two annotations.

    NOTE: (Boundary effects) While this method accounts for the 'background' at
    the start of the video before the first annotations, it doesn't account for
    the length of the background after the last annotation but before the end
    of the video.

    Args:
        annotations (dict): Maps filenames to groundtruth annotations.

    Returns:
        min_background_duration (int): Minimum duration (in frames) between two
            annotations.

    >>> SimpleAnnotation = collections.namedtuple(
    ...         'SimpleAnnotation', ['start_frame', 'end_frame'])
    >>> annotations = {'a': [SimpleAnnotation(3, 4), SimpleAnnotation(5, 6)]}
    >>> compute_min_background_duration(annotations)
    1
    >>> annotations = {'a': [SimpleAnnotation(2, 3), SimpleAnnotation(6, 7)]}
    >>> compute_min_background_duration(annotations)
    2
    """
    min_background_duration = float('inf')
    for filename, annotations in annotations.items():
        sorted_annotations = sorted(annotations,
                                    key=lambda x: (x.start_frame, x.end_frame))
        min_background_duration = min(min_background_duration,
                                      sorted_annotations[0].start_frame)
        for i in range(len(annotations) - 1):
            background_duration = (sorted_annotations[i + 1].start_frame -
                                   sorted_annotations[i].end_frame)
            min_background_duration = min(min_background_duration,
                                          background_duration)
    return min_background_duration


def compute_duration_mean_std(annotations):
    """
    Args:
        annotations (dict): Maps filenames to groundtruth annotations.

    Returns:
        mean, stderr of durations (in frames)
    """
    durations = get_durations(annotations)
    return durations.mean(), durations.std()


def annotations_to_frame_labels(annotations, num_frames):
    """
    Convert annotations for one category and one file to a binary label vector.

    Args:
        annotations (list of Annotation): These must correspond to exactly one
            file and one category.
        num_frames (int)

    Returns:
        frame_labels (np.array, shape (1, num_frames)): Binary vector
            indicating whether each frame is in an annotation.
    """
    if len(set([annotation.filename for annotation in annotations])) > 1:
        raise ValueError('Annotations should be for at most one filename.')
    if len(set([annotation.category for annotation in annotations])) > 1:
        raise ValueError('Annotations should be for at most one category.')

    frame_groundtruth = np.zeros((1, num_frames))
    for annotation in annotations:
        start, end = annotation.start_frame, annotation.end_frame
        frame_groundtruth[0, start:end + 1] = 1
    return frame_groundtruth.astype(int)


def compute_priors(training_annotations, class_list, frame_counts):
    """Compute P(category) prior for each category.

    Args:
        training_annotations (dict): Maps filenames to list of Annotation
            objects.
        class_list (list of strings)
        frame_counts (dict): Maps filename to number of frames.

    Returns:
        priors (np.array, shape (len(class_list), )): Prior for each category.
    """
    num_total_frames = sum(frame_counts.values())
    priors = np.zeros(len(class_list))
    for i, category in enumerate(class_list):
        category_annotations = filter_annotations_by_category(
            training_annotations, category)
        frame_label_sequences = [
            annotations_to_frame_labels(file_annotations,
                                        frame_counts[filename])
            for filename, file_annotations in category_annotations.items()
        ]
        num_category_frames = sum([sequence.sum()
                                   for sequence in frame_label_sequences])
        priors[i] = num_category_frames / num_total_frames
    return priors


def in_annotation(annotation, frame_index):
    return (annotation.start_frame <= frame_index <= annotation.end_frame)


def annotations_overlap(x, y):
    x_ends_before_y_starts = x.end_frame < y.start_frame
    x_starts_after_y_ends = x.start_frame > y.end_frame
    return not (x_ends_before_y_starts or x_starts_after_y_ends)


def compute_overlap_counts(annotations):
    """Count how often each action overlap occurs.

    Args:
        annotations (dict): Maps filename to list of Annotation objects.

    Returns:
        overlap_instance_counts (collections.Counter): Maps a set of categories
            to the number of instances where they overlapped (an instance is
            defined by the annotations that make up the overlap).


    >>> SimpleAnnotation = collections.namedtuple(
    ...         'SimpleAnnotation', ['start_frame', 'end_frame', 'category'])
    >>> overlaps = compute_overlap_counts({'1': [SimpleAnnotation(0, 2, 'a'),
    ...                                          SimpleAnnotation(1, 3, 'b')]})
    >>> assert overlaps[frozenset('a')] == 1
    >>> assert overlaps[frozenset('b')] == 1
    >>> assert overlaps[frozenset(['a', 'b'])] == 2
    """
    # Maps category set to set of unique instances.
    overlap_instances = collections.defaultdict(list)
    for filename, file_annotations in annotations.items():
        frames_to_consider = sorted(list(
            set([annotation.start_frame for annotation in file_annotations] +
                [annotation.end_frame for annotation in file_annotations])))
        for frame in frames_to_consider:
            current_annotations = [annotation
                                   for annotation in file_annotations
                                   if in_annotation(annotation, frame)]
            category_set = frozenset(x.category for x in current_annotations)
            instance = set((x.category, x.start_frame, x.end_frame)
                           for x in current_annotations)
            overlap_instances[category_set].append(instance)
    overlap_counts = {categories: len(instances)
                      for categories, instances in overlap_instances.items()}
    return overlap_counts
