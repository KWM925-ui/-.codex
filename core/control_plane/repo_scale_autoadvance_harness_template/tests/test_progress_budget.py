import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stack.front_end.progress_budget import choose_sample_count


class ProgressBudgetTest(unittest.TestCase):
    def test_structural_floor_is_respected(self) -> None:
        self.assertEqual(choose_sample_count(10.0, 0.25, 55), 55)

    def test_time_based_count_can_exceed_floor(self) -> None:
        self.assertEqual(choose_sample_count(28.0, 0.40, 60), 70)

    def test_invalid_parameters_raise(self) -> None:
        with self.assertRaises(ValueError):
            choose_sample_count(10.0, 0.0, 10)


if __name__ == "__main__":
    unittest.main()
