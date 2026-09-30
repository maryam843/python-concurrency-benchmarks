import unittest

from parallel_sum.threads import calculate_sum_parallel


class TestThreadingSum(unittest.TestCase):
    def test_sum(self):
        self.assertEqual(calculate_sum_parallel(10, 2)[0], 55)

if __name__ == '__main__':
    unittest.main()


