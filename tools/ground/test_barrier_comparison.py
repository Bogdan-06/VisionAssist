import unittest
from compare_barrier_android import compare,validate


def box(x=0,score=.8,category='stairs'):
    return {'class':category,'score':score,'box':[x,0,x+10,10]}


class ComparisonTests(unittest.TestCase):
    def test_order_and_small_numeric_rounding(self):
        result=compare([box(),box(30,category='curb')],
                       [box(30.5,.8003,'curb'),box(.4,.7998)],.3)
        self.assertTrue(result['passed'])
        self.assertEqual(result['matched_pairs'],2)

    def test_wrong_class_duplicate_and_bad_geometry_cannot_match(self):
        self.assertFalse(compare([box()],[box(category='curb')],.3)['passed'])
        self.assertFalse(compare([box()],[box(),box()],.3)['passed'])
        self.assertFalse(compare([box()],[box(3)],.3)['passed'])

    def test_global_assignment_handles_ambiguous_nearby_boxes(self):
        self.assertTrue(compare([box(10),box(12)],[box(11),box(9)],.3)['passed'])

    def test_borderline_outputs_do_not_hide_required_mismatches(self):
        self.assertTrue(compare([box(score=.3002)],[box(score=.2998)],.3)['passed'])
        self.assertFalse(compare([box(score=.4)],[],.3)['passed'])
        # Required endpoints must take priority over optional-only matches.
        result=compare([box(0,.3012),box(1,.2997)],
                       [box(1,.3003),box(0,.3005)],.3)
        self.assertTrue(result['passed'])
        self.assertTrue(compare([box(0,.3012)],[box(0,.3004),box(1,.3015)],.3)['passed'])

    def test_empty_result_has_no_fake_numeric_precision(self):
        result=compare([],[],.3)
        self.assertTrue(result['passed'])
        self.assertIsNone(result['max_score_error'])
        with self.assertRaises(ValueError): validate([box(score=float('nan'))],320,320)
        with self.assertRaises(ValueError): validate([box(315)],320,320)
        with self.assertRaises(ValueError): compare([],[],.3,pixel_tolerance=float('inf'))


if __name__=='__main__': unittest.main()
