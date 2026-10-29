"""Run with the isolated Model Maker Python, not the TF 2.20 mask environment."""
import unittest
from train_modelmaker import FiniteLosses


class FiniteLossTests(unittest.TestCase):
    def test_custom_loss_names_without_standard_loss_key(self):
        callback=FiniteLosses()
        callback.on_train_batch_end(0, {'total_loss': 2.0, 'cls_loss': 1.0, 'box_loss': 0.0})
        for name in ('total_loss','cls_loss','box_loss','model_loss'):
            for value in (float('nan'),float('inf'),float('-inf')):
                with self.subTest(name=name,value=value), self.assertRaises(FloatingPointError):
                    callback.on_train_batch_end(1,{name:value})

    def test_nonfinite_validation_is_rejected_before_checkpoint(self):
        callback=FiniteLosses()
        with self.assertRaisesRegex(FloatingPointError,'val_total_loss'):
            callback.on_epoch_end(0,{'total_loss':1.0,'val_total_loss':float('nan')})
        callback.on_epoch_end(0,{'total_loss':1.0,'val_total_loss':2.0})


if __name__=='__main__':
    unittest.main()
