import os
import pathlib
import tempfile
import unittest

from offline_brain import AshOfflineBrain


class OfflineBrainTests(unittest.TestCase):
    def test_micro_core_math_without_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get('ASH_LOCAL_HOME')
            os.environ['ASH_LOCAL_HOME'] = tmp
            try:
                brain = AshOfflineBrain()
                self.assertEqual(brain.respond('calculate 12 * (4 + 1)', remember=False), '60')
                self.assertFalse(brain.status().generative_ready)
            finally:
                if old is None: os.environ.pop('ASH_LOCAL_HOME', None)
                else: os.environ['ASH_LOCAL_HOME'] = old

    def test_local_memory_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get('ASH_LOCAL_HOME')
            os.environ['ASH_LOCAL_HOME'] = tmp
            try:
                brain = AshOfflineBrain()
                brain.memory.add('The project codename is Blackbird.', 'note')
                answer = brain.respond('What did we discuss about project codename Blackbird?', remember=False)
                self.assertIn('Blackbird', answer)
            finally:
                if old is None: os.environ.pop('ASH_LOCAL_HOME', None)
                else: os.environ['ASH_LOCAL_HOME'] = old

    def test_status_is_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = os.environ.get('ASH_LOCAL_HOME')
            os.environ['ASH_LOCAL_HOME'] = tmp
            try:
                status = AshOfflineBrain().status()
                self.assertEqual(status.mode, 'offline')
                self.assertIn(status.backend, {'python_micro_core', 'llama_cpp_direct'})
            finally:
                if old is None: os.environ.pop('ASH_LOCAL_HOME', None)
                else: os.environ['ASH_LOCAL_HOME'] = old


if __name__ == '__main__':
    unittest.main()
