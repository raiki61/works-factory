"""stats.py の単体テスト。parse_scores の悪い要素・load_scores・主経路はわざと試験しない。"""
import unittest

from stats import clamp, mean, median


class TestStats(unittest.TestCase):
    def test_mean_of_three(self):
        self.assertEqual(mean([1, 2, 3]), 2.0)

    def test_mean_of_empty_raises(self):
        with self.assertRaises(ValueError):
            mean([])

    def test_median_of_odd(self):
        self.assertEqual(median([3, 1, 2]), 2)

    def test_median_of_even(self):
        self.assertEqual(median([1, 2, 3, 4]), 2.5)

    def test_median_of_empty_raises(self):
        with self.assertRaises(ValueError):
            median([])

    def test_clamp_within_range(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_clamp_above_range(self):
        self.assertEqual(clamp(15, 0, 10), 10)

    def test_clamp_below_range(self):
        self.assertEqual(clamp(-5, 0, 10), 0)


if __name__ == "__main__":
    unittest.main()
