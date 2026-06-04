import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stack.front_end.progress_budget import choose_sample_count


class WideningBudgetTest(unittest.TestCase):
    def test_widened_scene_budget(self) -> None:
        self.assertEqual(choose_sample_count(33.6, 0.42, 60), 80)

    def test_shorter_scene_keeps_floor(self) -> None:
        self.assertEqual(choose_sample_count(12.0, 0.4, 55), 55)

    def test_invalid_params_still_raise(self) -> None:
        with self.assertRaises(ValueError):
            choose_sample_count(10.0, 0.0, 10)


if __name__ == "__main__":
    unittest.main()
