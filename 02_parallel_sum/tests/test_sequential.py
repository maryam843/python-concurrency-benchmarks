import unittest

from parallel_sum.functions import calculate_sum_sequential


class TestSequentialSum(unittest.TestCase):
    def test_sum(self):
        self.assertEqual(calculate_sum_sequential(10)[0], 55)

if __name__ == '__main__':
    unittest.main()
