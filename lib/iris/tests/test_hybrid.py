# (C) British Crown Copyright 2010 - 2014, Met Office
#
# This file is part of Iris.
#
# Iris is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Iris is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Iris.  If not, see <http://www.gnu.org/licenses/>.
"""
Test the hybrid vertical coordinate representations.

"""

# import iris tests first so that some things can be initialised before
# importing anything else
import iris.tests as tests

import warnings

import numpy as np

from iris.aux_factory import HybridHeightFactory, HybridPressureFactory
import iris
import iris.tests.stock


class TestRealistic4d(tests.GraphicsTest):
    def setUp(self):
        self.cube = iris.tests.stock.realistic_4d()
        self.altitude = self.cube.coord('altitude')

    def test_metadata(self):
        self.assertEqual(self.altitude.units, 'm')
        self.assertIsNone(self.altitude.coord_system)
        self.assertEqual(self.altitude.attributes, {'positive': 'up'})

    def test_points(self):
        self.assertAlmostEqual(self.altitude.points.min(), np.float32(191.84892))
        self.assertAlmostEqual(self.altitude.points.max(), np.float32(40000))

    def test_transpose(self):
        self.assertCML(self.cube, ('stock', 'realistic_4d.cml'))
        self.cube.transpose()
        self.assertCML(self.cube, ('derived', 'transposed.cml'))

    def test_indexing(self):
        cube = self.cube[:, :, 0, 0]
        # Make sure the derived 'altitude' coordinate survived the indexing.
        altitude = cube.coord('altitude')
        self.assertCML(cube, ('derived', 'column.cml'))

    def test_removing_sigma(self):
        # Check the cube remains OK when sigma is removed.
        cube = self.cube
        cube.remove_coord('sigma')
        self.assertCML(cube, ('derived', 'removed_sigma.cml'))
        self.assertString(str(cube), ('derived', 'removed_sigma.__str__.txt'))

        # Check the factory now only has surface_altitude and delta dependencies.
        factory = cube.aux_factory(name='altitude')
        t = [key for key, coord in factory.dependencies.iteritems() if coord is not None]
        self.assertItemsEqual(t, ['orography', 'delta'])

    def test_removing_orography(self):
        # Check the cube remains OK when the orography is removed.
        cube = self.cube
        cube.remove_coord('surface_altitude')
        self.assertCML(cube, ('derived', 'removed_orog.cml'))
        self.assertString(str(cube), ('derived', 'removed_orog.__str__.txt'))

        # Check the factory now only has sigma and delta dependencies.
        factory = cube.aux_factory(name='altitude')
        t = [key for key, coord in factory.dependencies.iteritems() if coord is not None]
        self.assertItemsEqual(t, ['sigma', 'delta'])

    def test_derived_coords(self):
        derived_coords = self.cube.derived_coords
        self.assertEqual(len(derived_coords), 1)
        altitude = derived_coords[0]
        self.assertEqual(altitude.standard_name, 'altitude')
        self.assertEqual(altitude.attributes, {'positive': 'up'})

    def test_aux_factory(self):
        factory = self.cube.aux_factory(name='altitude')
        self.assertEqual(factory.standard_name, 'altitude')
        self.assertEqual(factory.attributes, {'positive': 'up'})

    def test_aux_factory_var_name(self):
        factory = self.cube.aux_factory(name='altitude')
        factory.var_name = 'alt'
        factory = self.cube.aux_factory(var_name='alt')
        self.assertEqual(factory.standard_name, 'altitude')
        self.assertEqual(factory.attributes, {'positive': 'up'})

    def test_no_orography(self):
        # Get rid of the normal hybrid-height factory.
        cube = self.cube
        factory = cube.aux_factory(name='altitude')
        cube.remove_aux_factory(factory)

        # Add a new one which only references level_height & sigma.
        delta = cube.coord('level_height')
        sigma = cube.coord('sigma')
        factory = HybridHeightFactory(delta, sigma)
        cube.add_aux_factory(factory)

        self.assertEqual(len(cube.aux_factories), 1)
        self.assertEqual(len(cube.derived_coords), 1)
        self.assertString(str(cube), ('derived', 'no_orog.__str__.txt'))
        self.assertCML(cube, ('derived', 'no_orog.cml'))

    def test_invalid_dependencies(self):
        # Must have either delta or orography
        with self.assertRaises(ValueError):
            factory = HybridHeightFactory()
        sigma = self.cube.coord('sigma')
        with self.assertRaises(ValueError):
            factory = HybridHeightFactory(sigma=sigma)

        # Orography must not have bounds
        with warnings.catch_warnings():
            # Cause all warnings to raise Exceptions
            warnings.simplefilter("error")
            with self.assertRaises(UserWarning):
                factory = HybridHeightFactory(orography=sigma)

    def test_bounded_orography(self):
        # Start with everything normal
        orog = self.cube.coord('surface_altitude')
        altitude = self.cube.coord('altitude')
        self.assertIsInstance(altitude.bounds, np.ndarray)

        # Make sure altitude still works OK if orography was messed
        # with *after* altitude was created.
        altitude = self.cube.coord('altitude')
        orog.bounds = np.zeros(orog.shape + (4,))
        self.assertIsInstance(altitude.bounds, np.ndarray)

        # Make sure altitude.bounds now raises an error.
        altitude = self.cube.coord('altitude')
        with self.assertRaises(ValueError):
            bounds = altitude.bounds


class TestHybridPressure(tests.IrisTest):
    def setUp(self):
        # Convert the hybrid-height into hybrid-pressure...
        cube = iris.tests.stock.realistic_4d()

        # Get rid of the normal hybrid-height factory.
        factory = cube.aux_factory(name='altitude')
        cube.remove_aux_factory(factory)

        # Mangle the height coords into pressure coords.
        delta = cube.coord('level_height')
        delta.rename('level_pressure')
        delta.units = 'Pa'
        sigma = cube.coord('sigma')
        ref = cube.coord('surface_altitude')
        ref.rename('surface_air_pressure')
        ref.units = 'Pa'

        factory = HybridPressureFactory(delta, sigma, ref)
        cube.add_aux_factory(factory)
        self.cube = cube
        self.air_pressure = self.cube.coord('air_pressure')

    def test_metadata(self):
        self.assertEqual(self.air_pressure.units, 'Pa')
        self.assertIsNone(self.air_pressure.coord_system)
        self.assertEqual(self.air_pressure.attributes, {})

    def test_points(self):
        points = self.air_pressure.points
        self.assertEqual(points.dtype, np.float32)
        self.assertAlmostEqual(points.min(), np.float32(191.84892))
        self.assertAlmostEqual(points.max(), np.float32(40000))

        # Convert the reference surface to float64 and check the
        # derived coordinate becomes float64.
        temp = self.cube.coord('surface_air_pressure').points
        temp = temp.astype('f8')
        self.cube.coord('surface_air_pressure').points = temp
        points = self.cube.coord('air_pressure').points
        self.assertEqual(points.dtype, np.float64)
        self.assertAlmostEqual(points.min(), 191.8489257)
        self.assertAlmostEqual(points.max(), 40000)

    def test_invalid_dependencies(self):
        # Must have either delta or surface_air_pressure
        with self.assertRaises(ValueError):
            factory = HybridPressureFactory()
        sigma = self.cube.coord('sigma')
        with self.assertRaises(ValueError):
            factory = HybridPressureFactory(sigma=sigma)

        # Surface pressure must not have bounds
        with warnings.catch_warnings():
            # Cause all warnings to raise Exceptions
            warnings.simplefilter("error")
            with self.assertRaises(UserWarning):
                factory = HybridPressureFactory(
                    sigma=sigma, surface_air_pressure=sigma)

    def test_bounded_surface_pressure(self):
        # Start with everything normal
        surface_pressure = self.cube.coord('surface_air_pressure')
        pressure = self.cube.coord('air_pressure')
        self.assertIsInstance(pressure.bounds, np.ndarray)

        # Make sure pressure still works OK if surface pressure was messed
        # with *after* pressure was created.
        pressure = self.cube.coord('air_pressure')
        surface_pressure.bounds = np.zeros(surface_pressure.shape + (4,))
        self.assertIsInstance(pressure.bounds, np.ndarray)

        # Make sure pressure.bounds now raises an error.
        pressure = self.cube.coord('air_pressure')
        with self.assertRaises(ValueError):
            bounds = pressure.bounds


class TestHybridPressureWithReferencePressure(TestHybridPressure):
    def setUp(self):
	# Convert the "p = ap + b * ps" form to "p = a * p0 + b * ps"
	super(TestHybridPressureWithReferencePressure, self).setUp()

	# Construct a scalar reference pressure coordinate (1000hPa)
	ref = iris.coords.AuxCoord( np.float32(1e5),
				    long_name='reference_air_pressure',
				    units='Pa' )
	self.cube.add_aux_coord(ref)

        # Get rid of the existing hybrid-pressure factory.
        factory = self.cube.aux_factory(name='air_pressure')
        self.cube.remove_aux_factory(factory)

        # Mangle the level pressure coord into a dimensionless one
        delta = self.cube.coord('level_pressure')
        delta.rename('delta')
        delta.units = '1'
	delta = delta.copy(points = delta.points / ref.points,
			   bounds = delta.bounds / ref.points)
	self.cube.replace_coord(delta)

        sigma = self.cube.coord('sigma')
        surf = self.cube.coord('surface_air_pressure')

        factory = HybridPressureFactory(delta, sigma, surf, ref)
        self.cube.add_aux_factory(factory)
        self.air_pressure = self.cube.coord('air_pressure')

    def test_invalid_dependencies(self):
        # Must have either delta or surface_air_pressure
        ref = self.cube.coord('reference_air_pressure')
        with self.assertRaises(ValueError):
            factory = HybridPressureFactory(reference_pressure=ref)

        # Reference pressure must not have bounds
        sigma = self.cube.coord('sigma')
        with warnings.catch_warnings():
            # Cause all warnings to raise Exceptions
            warnings.simplefilter("error")
            with self.assertRaises(UserWarning):
                factory = HybridPressureFactory(reference_pressure=sigma)


if __name__ == "__main__":
    tests.main()
