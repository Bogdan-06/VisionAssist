"""Small numerical checks for mask-derived labels and coverage accounting."""
import unittest
import numpy as np
from evaluate_masked_videos import mask_boxes, covered_pixels
from detection_metrics import match


class MaskEvaluationTest(unittest.TestCase):
    def test_retains_small_disconnected_region_and_threshold_boundary(self):
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        image[1:4, 2:6] = 255
        image[8, 8] = 128
        image[8, 1] = 127
        mask, boxes, areas = mask_boxes(image)
        self.assertEqual(int(mask.sum()), 13)
        self.assertCountEqual(boxes, [[2, 1, 6, 4], [8, 8, 9, 9]])
        self.assertCountEqual(areas, [12, 1])

    def test_duplicate_boxes_do_not_duplicate_pixel_coverage(self):
        truth = np.zeros((10, 10), dtype=bool); truth[2:6, 2:6] = True
        predictions = [dict(score=.9, box=[0, 0, 4, 4]), dict(score=.8, box=[0, 0, 4, 4])]
        self.assertEqual(covered_pixels(predictions, .3, truth), (4, 16, 16))
        self.assertEqual(covered_pixels(predictions, .95, truth), (0, 0, 16))

    def test_one_detection_cannot_match_two_mask_components(self):
        predictions = [dict(score=.9, box=[0, 0, 4, 4]), dict(score=.8, box=[0, 0, 4, 4])]
        self.assertEqual(match(predictions, [[0, 0, 4, 4], [8, 8, 9, 9]], [], .3), (1, 1, 1))


if __name__ == '__main__': unittest.main()
