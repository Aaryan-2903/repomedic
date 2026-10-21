import unittest
from calc import add, subtract, multiply, divide

class TestCalculator(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)
        self.assertEqual(add(-1, 1), 0)

    def test_subtract(self):
        self.assertEqual(subtract(5, 2), 3)

    def test_multiply(self):
        self.assertEqual(multiply(3, 4), 12)

    def test_divide_regular(self):
        self.assertEqual(divide(10, 2), 5.0)

    def test_divide_fractional(self):
        # This will fail on integer floor division (5 // 2 = 2 != 2.5)
        self.assertAlmostEqual(divide(5, 2), 2.5)

    def test_divide_negative_fractional(self):
        # This fails (-7 // 2 = -4 != -3.5)
        self.assertAlmostEqual(divide(-7, 2), -3.5)

    def test_divide_by_zero(self):
        with self.assertRaises(ValueError):
            divide(10, 0)

if __name__ == '__main__':
    unittest.main()
