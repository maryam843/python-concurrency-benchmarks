"""
Unit tests for connection pool.

"""

import unittest

from connection_pool.connection_pool import ConnectionPool


class TestConnectionPool(unittest.TestCase):

    def setUp(self):
        self.pool = ConnectionPool(size=2)

    def tearDown(self):
        self.pool.shutdown()

    def test_get_connection(self):
        conn1 = self.pool.get_connection()
        conn2 = self.pool.get_connection()
        self.assertIn(conn1, ["DB_Conn_0", "DB_Conn_1"])
        self.assertIn(conn2, ["DB_Conn_0", "DB_Conn_1"])
        self.assertNotEqual(conn1, conn2)
        # the pool is empty: a blocking get would wait, so use a short timeout
        self.assertIsNone(self.pool.get_connection(timeout=0.1))

    def test_release_connection(self):
        # the earlier version asserted the same connection comes back, but the queue is FIFO and hands
        # out the other free connection first. What matters is that the released one is usable again.
        conn = self.pool.get_connection()
        self.pool.release_connection(conn)
        conn2 = self.pool.get_connection()
        conn3 = self.pool.get_connection()
        self.assertEqual({conn2, conn3}, {"DB_Conn_0", "DB_Conn_1"})
        self.assertEqual(self.pool.max_concurrent_holders, 2)


if __name__ == "__main__":
    unittest.main()
