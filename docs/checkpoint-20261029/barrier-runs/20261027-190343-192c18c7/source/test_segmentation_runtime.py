"""Coordinate/region edge cases for mask-derived evaluation regions."""
import unittest
import numpy as np
from segmentation_runtime import prepare, restore, components


class SegmentationGeometryTest(unittest.TestCase):
    def test_padding_predictions_do_not_become_scene_regions(self):
        for shape, axis in (((160,320,3),0),((320,160,3),1)):
            _, transform = prepare(np.zeros(shape,np.uint8))
            output = np.zeros((80,80),np.float32)
            if axis == 0:
                output[:20,:] = 1  # Entire top padding, outside the real image.
            else:
                output[:,:20] = 1  # Entire left padding, outside the real image.
            restored = restore(output,transform)
            self.assertEqual(restored.shape,shape[:2])
            # Bilinear boundary interpolation may bleed below 0.5, but no positive
            # padding region may survive the defined 0.5 mask threshold.
            self.assertEqual(components(restored,.5),[])

    def test_tiny_regions_are_retained_and_sorted_without_box_inflation(self):
        probability = np.zeros((12,15),np.float32)
        probability[2,3] = .9
        probability[7:9,10:13] = .6
        actual = components(probability,.5)
        self.assertEqual([v['box'] for v in actual],[[3,2,4,3],[10,7,13,9]])
        self.assertEqual([v['area_pixels'] for v in actual],[1,6])
        self.assertAlmostEqual(actual[0]['score'],.9,places=6)
        self.assertAlmostEqual(actual[1]['score'],.6,places=6)

    def test_rgb_order_and_invalid_probabilities(self):
        rgb = np.zeros((320,320,3),np.uint8)
        rgb[...,0] = 255
        prepared, transform = prepare(rgb)
        np.testing.assert_array_equal(prepared[0,0],[1,-1,-1])
        invalid = np.zeros((80,80),np.float32)
        invalid[20,20] = np.nan
        with self.assertRaises(ValueError):
            restore(invalid,transform)


if __name__=='__main__':
    unittest.main()
