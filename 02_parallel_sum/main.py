# entry point for execution: python 02_parallel_sum/main.py [n] [workers]

import sys

from parallel_sum.functions import calculate_sum_sequential
from parallel_sum.laws import amdahl_speedup, gustafson_speedup
from parallel_sum.processing import calculate_sum_multiprocessing
from parallel_sum.threads import calculate_sum_parallel


def evaluate_performance(n, num_threads, num_processes):

    # Sequential Execution
    seq_sum, seq_time = calculate_sum_sequential(n)
    print(f"Sequential Sum: {seq_sum}")
    print(f"Sequential Execution Time: {seq_time:.4f} seconds")
    print("___________________")

    # Threaded Execution
    par_sum, par_time = calculate_sum_parallel(n, num_threads)
    print(f"Threaded Sum: {par_sum}")
    print(f"Threaded Execution Time: {par_time:.4f} seconds")
    print("___________________")

    # Process Execution
    pro_sum, pro_time = calculate_sum_multiprocessing(n, num_processes)
    print(f"Process Sum: {pro_sum}")
    print(f"Process Execution Time: {pro_time:.4f} seconds")
    print("___________________")

    # Check if sums match (and match the closed form n(n+1)/2)
    if seq_sum == par_sum == pro_sum == n * (n + 1) // 2:
        # Calculate Speedups
        speedup_thread = seq_time / par_time
        speedup_process = seq_time / pro_time

        # Efficiency
        efficiency_thread = speedup_thread / num_threads
        efficiency_process = speedup_process / num_processes

        # Amdahl's and Gustafson's laws (assuming 90% parallelizable)
        P = 0.9
        print(f"Thread Speedup: {speedup_thread:.2f}")
        print(f"Process Speedup: {speedup_process:.2f}")

        print(f"Thread Efficiency: {efficiency_thread:.2f}")
        print(f"Process Efficiency: {efficiency_process:.2f}")

        print(f"Amdahl's Speedup (Thread): {amdahl_speedup(P, num_threads):.2f}")
        print(f"Amdahl's Speedup (Process): {amdahl_speedup(P, num_processes):.2f}")

        print(f"Gustafson's Speedup (Thread): {gustafson_speedup(P, num_threads):.2f}")
        print(f"Gustafson's Speedup (Process): {gustafson_speedup(P, num_processes):.2f}")
        return True
    print("Error: The sums do not match!")
    return False


if __name__ == "__main__":
    large_number = int(float(sys.argv[1])) if len(sys.argv) > 1 else 10**6
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    ok = evaluate_performance(large_number, workers, workers)
    sys.exit(0 if ok else 1)
