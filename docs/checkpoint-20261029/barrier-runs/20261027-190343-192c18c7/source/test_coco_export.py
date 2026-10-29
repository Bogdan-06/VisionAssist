import unittest
from export_coco import select_records, annotations_for


class ExportTest(unittest.TestCase):
    def record(self, **changes):
        result=dict(id='sample',split='train',used_for_training=True,ignored=[],
                    boxes=[[1.,2.,11.,22.]],width=40,height=30)
        result.update(changes)
        return result

    def test_xywh_conversion_preserves_area_and_coordinates(self):
        row=annotations_for(self.record(),7,12)[0]
        self.assertEqual([1.,2.,10.,20.],row['bbox'])
        self.assertEqual((200.,7,12,1),(row['area'],row['image_id'],row['id'],row['category_id']))
        with self.assertRaises(ValueError): annotations_for(self.record(boxes=[[0,0,50,10]]),0,0)

    def test_training_export_excludes_unused_and_test_images_but_keeps_negatives(self):
        records=[self.record(boxes=[]),self.record(id='unused',used_for_training=False),
                 self.record(id='heldout',split='test',used_for_training=False)]
        self.assertEqual([records[0]],select_records(dict(records=records),'train'))
        with self.assertRaises(ValueError): select_records(dict(records=records),'test')

    def test_split_leakage_and_ambiguous_annotations_fail(self):
        for record in [self.record(split='validation'),self.record(ignored=[[0,0,1,1]])]:
            with self.assertRaises(ValueError): select_records(dict(records=[record]),'train')


if __name__ == '__main__': unittest.main()
