import unittest
from tumor_volume import calculate_tumor_volume


class TestTumorVolume(unittest.TestCase):

    def test_normal_values(self):
        result = calculate_tumor_volume(10, 5)
        self.assertEqual(result, 125)

    def test_equal_length_and_width(self):
        result = calculate_tumor_volume(6, 6)
        self.assertEqual(result, 108)

    def test_decimal_values(self):
        result = calculate_tumor_volume(10.5, 5.2)
        self.assertAlmostEqual(result, 141.96)

    def test_width_greater_than_length(self):
        with self.assertRaises(ValueError):
            calculate_tumor_volume(5, 10)

    def test_string_length(self):
        with self.assertRaises(ValueError):
            calculate_tumor_volume("abc", 5)

    def test_string_width(self):
        with self.assertRaises(ValueError):
            calculate_tumor_volume(10, "abc")


if __name__ == "__main__":
    unittest.main()