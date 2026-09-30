import unittest
from parallel_sum.shared_array import parallel_process_sum

class TestMultiprocessingSum(unittest.TestCase):
    def test_sum(self):
        self.assertEqual(parallel_process_sum(10, 2), 55)

if __name__ == '__main__':
    unittest.main()
