"""Metric contract tests: matching errors can otherwise make a poor detector look better."""
import unittest
from detection_metrics import iou, match


class MatchingTest(unittest.TestCase):
    def test_duplicates_are_false_positives(self):
        box=[10,10,20,20]
        self.assertEqual((1,1,0),match([dict(score=.9,box=box),dict(score=.8,box=box)],[box],[],.5))

    def test_missed_and_ignored_boxes(self):
        self.assertEqual((0,0,1),match([dict(score=.9,box=[30,30,40,40])],[[0,0,10,10]],[[30,30,40,40]],.5))
        self.assertEqual((0,1,1),match([dict(score=.9,box=[50,50,60,60])],[[0,0,10,10]],[[30,30,40,40]],.5))

    def test_score_filter_and_nonoverlap(self):
        self.assertEqual((0,0,1),match([dict(score=.2,box=[0,0,10,10])],[[0,0,10,10]],[],.5))
        self.assertEqual(0,iou([0,0,10,10],[10,10,20,20]))
        self.assertEqual(1,iou([0,0,10,10],[0,0,10,10]))


if __name__=='__main__': unittest.main()
