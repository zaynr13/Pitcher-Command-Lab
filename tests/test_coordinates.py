import unittest
import pandas as pd
from scripts.external_evaluation import to_front


class CoordinateTests(unittest.TestCase):
    def test_constant_velocity_plane_transport(self):
        # Synthetic geometry fixture, never application player data.
        d = pd.DataFrame(
            [
                dict(
                    plate_x=0.2,
                    plate_z=2.0,
                    vx0=10.0,
                    vy0=-100.0,
                    vz0=-5.0,
                    ax=0.0,
                    ay=0.0,
                    az=0.0,
                )
            ]
        )
        r = to_front(d)
        dt = -(17 / 24) / 100
        self.assertAlmostEqual(r.plate_x.iloc[0], 0.2 + 10 * dt)
        self.assertAlmostEqual(r.plate_z.iloc[0], 2 - 5 * dt)
        self.assertEqual(d.plate_z.iloc[0], 2.0)

    def test_no_horizontal_motion_preserves_x(self):
        d = pd.DataFrame(
            [
                dict(
                    plate_x=-0.4,
                    plate_z=2.0,
                    vx0=0.0,
                    vy0=-130.0,
                    vz0=-5.0,
                    ax=0.0,
                    ay=30.0,
                    az=-20.0,
                )
            ]
        )
        r = to_front(d)
        self.assertEqual(r.plate_x.iloc[0], -0.4)
        self.assertGreater(r.plate_z.iloc[0], 2.0)


if __name__ == "__main__":
    unittest.main()
