import unittest

from collect_uvm_first_matrix import coverage


def tick(time, result=0):
    return {'parent': {'observed_ns': time}, 'tick': {'cuda_result': result}}


class PeerCoverageTest(unittest.TestCase):
    def test_bracketed_successful_ticks_cover_phase(self):
        report = coverage(1_050_000_000, 1_350_000_000,
                          [tick(1_000_000_000), tick(1_200_000_000), tick(1_400_000_000)])
        self.assertEqual(report['coveringPeerTicks'], 3)
        self.assertEqual(report['maxGapNs'], 200_000_000)

    def test_distant_successes_cannot_cover_phase(self):
        with self.assertRaises(AssertionError):
            coverage(5_000_000_000, 6_000_000_000, [tick(0), tick(10_000_000_000)])

    def test_failure_or_missing_boundary_cannot_pass(self):
        for ticks in ([tick(1_000_000_000), tick(1_200_000_000, 2), tick(1_400_000_000)],
                      [tick(1_200_000_000), tick(1_400_000_000)],
                      [tick(1_000_000_000), tick(1_200_000_000)]):
            with self.assertRaises(AssertionError):
                coverage(1_050_000_000, 1_350_000_000, ticks)


if __name__ == '__main__':
    unittest.main()
