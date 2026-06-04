import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from stack.front_end.progress_budget import choose_sample_count


class RepeatabilityBudgetTest(unittest.TestCase):
    def test_same_inputs_repeat_stably(self) -> None:
        first = choose_sample_count(20.0, 0.4, 55)
        second = choose_sample_count(20.0, 0.4, 55)
        self.assertEqual(first, 55)
        self.assertEqual(second, 55)
        self.assertEqual(first, second)

    def test_high_budget_case_repeats(self) -> None:
        first = choose_sample_count(28.0, 0.4, 60)
        second = choose_sample_count(28.0, 0.4, 60)
        self.assertEqual(first, 70)
        self.assertEqual(second, 70)


if __name__ == "__main__":
    unittest.main()
