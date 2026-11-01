"""Dataset leakage and command contract tests without importing ML runtimes."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import visionassist_training as controller

from experiment_store import atomic_json
from visionassist_training import validate_splits, evaluation_commands


class ControllerTests(unittest.TestCase):
    def test_missing_output_drive_fails_without_looping(self):
        class MissingRoot:
            def exists(self): return False
            @property
            def parent(self): return self
            def __str__(self): return 'unavailable-drive'
        with self.assertRaisesRegex(FileNotFoundError,'unavailable'):
            controller.output_parent(MissingRoot())
    def test_duplicate_group_across_split_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'barrier-prepared-v1').mkdir()
            records=[dict(image='a',group='same',split='train'),dict(image='b',group='same',split='test'),
                     dict(image='c',group='other',split='validation')]
            atomic_json(root/'barrier-prepared-v1/manifest.json',dict(records=records))
            with self.assertRaisesRegex(ValueError,'Cross-split leakage'):
                validate_splits(root,'barrier')

    def test_test_arrays_cannot_enter_fitting(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'masked-segmentation-v1').mkdir()
            atomic_json(root/'masked-segmentation-v1/manifest.json',dict(records=[
                dict(id='a',split='test',training_arrays={'path':'test.npz'})]))
            with self.assertRaisesRegex(ValueError,'Held-out test'):
                validate_splits(root,'pothole')

    def test_bounded_barrier_evaluation_preserves_split(self):
        args=SimpleNamespace(task='barrier',data_root=Path('data'),evaluation_python=Path('python'),
                             split='validation',max_images=4)
        commands=list(evaluation_commands(args,Path('model.tflite'),Path('source'),Path('new')))
        self.assertEqual(len(commands),1)
        self.assertEqual(commands[0][1][-2:],['--max-images','4'])
        self.assertIn('validation',commands[0][1])
        self.assertNotIn('test',commands[0][1])

    def arguments(self, root, task, action):
        return SimpleNamespace(task=task,action=action,data_root=root/'data',output_root=root/'runs',
            evaluation_python=Path('python'),backbone=root/'backbone.h5',lock_file=root/'lock',
            epochs=7,batch_size=2,cache_batch_size=4,threads=2,device='cpu',split='all',
            max_images=None,run=None,checkpoint=None,report_file=None,smoke=False)

    def test_both_train_profiles_dispatch_existing_trainers_then_evaluators(self):
        for task in ('pothole','barrier'):
            with self.subTest(task=task),tempfile.TemporaryDirectory() as temp:
                args=self.arguments(Path(temp),task,'train')
                with patch.object(controller,'check',return_value={}),patch.object(controller,'ensure_no_trainer'), \
                     patch.object(controller,'run_step') as run_step:
                    controller.execute(args)
                command=run_step.call_args_list[0].args[0]
                expected='train_modelmaker.py' if task=='barrier' else 'train_masked_segmentation.py'
                self.assertEqual(Path(command[2]).name,expected)
                self.assertEqual(command[command.index('--epochs')+1],'7')
                self.assertEqual(command[command.index('--batch-size')+1],'2')
                self.assertNotIn('test',command)
                experiments=list(args.output_root.iterdir())
                self.assertEqual(len(experiments),1)
                self.assertEqual(controller.read_json(experiments[0]/'status.json')['state'],'completed')

    def test_resume_uses_a_new_directory_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as temp:
            args=self.arguments(Path(temp),'pothole','resume')
            args.run=Path(temp)/'previous'
            args.run.mkdir()
            (args.run/'marker').write_text('preserve')
            with patch.object(controller,'check',return_value={}),patch.object(controller,'ensure_no_trainer'), \
                 patch.object(controller,'run_step') as run_step:
                controller.execute(args)
            command=run_step.call_args_list[0].args[0]
            self.assertEqual(command[command.index('--resume-from')+1],str(args.run/'training'))
            self.assertEqual((args.run/'marker').read_text(),'preserve')

    def test_interruption_is_recorded_and_not_retried(self):
        with tempfile.TemporaryDirectory() as temp:
            args=self.arguments(Path(temp),'barrier','train')
            with patch.object(controller,'check',return_value={}),patch.object(controller,'ensure_no_trainer'), \
                 patch.object(controller,'run_step',side_effect=KeyboardInterrupt) as run_step:
                with self.assertRaises(KeyboardInterrupt):
                    controller.execute(args)
            self.assertEqual(run_step.call_count,1)
            run=next(args.output_root.iterdir())
            self.assertEqual(controller.read_json(run/'status.json')['state'],'interrupted')


if __name__=='__main__':
    unittest.main()
