"""Sequential sum of 1..n (from my L3-P1 code)."""

import time


def calculate_sum_sequential(n):
    start_time = time.perf_counter()
    total_sum = sum(range(1, n + 1))
    end_time = time.perf_counter()
    execution_time = end_time - start_time
    return total_sum, execution_time
