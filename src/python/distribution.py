"""Initial particle distribution construction kit."""

from __future__ import division

__copyright__ = "Copyright (C) 2007, 2008 Andreas Kloeckner"

__license__ = """
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see U{http://www.gnu.org/licenses/}.
"""



import numpy
import numpy.linalg as la
import pyrticle.tools
import pytools.log




class ParticleDistribution(object):
    def count_axes(self):
        """Return a 4-tuple, as (x_axes, v_axes, q_axes, m_axes).

        Each of the ?_axes variables specifies how many axes of

        * the position
        * the velocity
        * the particle charge
        * the particle mass

        are supplied by this distribution.
        """
        return (0,0,0,0)

    def make_particle(self):
        return ([],[],[],[])
        
    def mean(self):
        return ([],[],[],[])

    def get_rho_distrib(self):
        """Get a 1-normalized distribution function for the charge density."""
        raise NotImplementedError

    def get_rho_interpolant(self, discr, total_charge, err_thresh=0.2):
        rho_norm_1 = \
                * discr.interpolate_volume_function(self.get_rho_distrib())

        # check for correctness
        from hedge.discretization import integral
        int_rho_norm_1 = integral(discr, rho_norm_1)

        if abs(int_rho-total_charge)> err_thresh:
            raise RuntimeError("analytic charge density imprecise (relerr=%g)" % rel_err)

        return rho_dist * total_charge

    def add_to(self, cloud, nparticles):
        x_axes, v_axes, q_axes, m_axes = self.count_axes()

        assert x_axes == cloud.dimensions_pos
        assert v_axes == cloud.dimensions_velocity
        assert q_axes == 1
        assert m_axes == 1

        positions = []
        velocities = []
        charges = []
        masses = []

        result = (positions, velocities, charges, masses)

        for i in range(nparticles):
            particle = self.make_particle(nparticles)

            for res_property, particle_property in zip(result, particle):
                res_property.append(particle_property)

        cloud.add_particles(positions, velocities, charges, masses)




# joint distributions ---------------------------------------------------------
class JointParticleDistribution(ParticleDistribution):
    def __init__(self, distributions):
        self.distributions = distributions
        self.contributors = [
            [d for d in self.distributions() if d.count_axes()[component]]
            for component in range(4)]

    def count_axes(self):
        def add_tuples(x, y): 
            return tuple(xi+yi for xi, yi in zip(x, y))

        return reduce(add_tuples, (d.count_axes() for d in self.distributions))

    def make_particle(self):
        dist_to_part = dict((d, d.make_particle()) for d in self.distributions)
        return tuple(
                [].extend(dist_to_part[d][component] 
                    for d in self.contributors[component])
                for component in range(4))

    def mean(self):
        dist_to_part = dict((d, d.mean()) for d in self.distributions)
        return tuple(
                [].extend(dist_to_part[d][component] 
                    for d in self.contributors[component])
                for component in range(4))

    def get_rho_distrib(self):
        slices = []
        i = 0
        for d in self.contributors[0]:
            d_x_count = d.count_axes()[0]
            slices.append(slice(i, i+d_x_count))
            i += d_x_count

        from pytools import product

        x_funcs = [d.get_rho_distrib() for d in self.contributors[0]]
        funcs_and_slices = list(zip(x_funcs, slices))

        def f(x):
            return product(f(x[sl]) for f, sl in funcs_and_slices)

        return f




# delta distributions ---------------------------------------------------------
class DeltaVelocity(ParticleDistribution):
    def __init__(self, velocity):
        self.velocity = velocity

    def count_axes(self):
        return (0, len(self.velocity), 0, 0)

    def make_particle(self):
        return [[], self.velocity, [], []]
    mean = make_particle
        




class DeltaCharge(ParticleDistribution):
    def __init__(self, particle_charge):
        self.particle_charge = particle_charge

    def count_axes(self):
        return (0, 0, 1, 0)

    def make_particle(self):
        return [[], [], [self.particle_charge], []]
    mean = make_particle



class DeltaMass(ParticleDistribution):
    def __init__(self, particle_mass):
        self.particle_mass = particle_mass

    def count_axes(self):
        return (0, 0, 0, 1)

    def make_particle(self):
        return [[], [], [], [self.particle_mass]]
    mean = make_particle

    def particle_mass(self):
        return self.particle_mass



class DeltaChargeMass(ParticleDistribution):
    def __init__(self, particle_charge, particle_mass):
        self.particle_charge = particle_charge
        self.particle_mass = particle_mass

    def count_axes(self):
        return (0, 0, 1, 1)

    def make_particle(self):
        return [[], [], [self.particle_charge], [self.particle_mass]]
    mean = make_particle




# uniform distributions -------------------------------------------------------
class UniformPos(ParticleDistribution):
    def __init__(self, lower, uppper):
        self.lower = lower
        self.upper = upper
        self.zipped = list(zip(self.lower, self.uppper))

    def count_axes(self):
        return (len(self.lower), 0, 0, 0)

    def make_particle(self, count=None):
        from random import uniform
        return [[uniform(l, h) for l, h in self.zipped], [], [], []]
        
    def mean(self, count):
        return [[(l+h)/2 for l, h in self.zipped], [], [], []]

    def get_rho_distrib(self):
        compdata = [i, l, h 
        for i, (l, h) in enumerate(zip(self.lower, self.upper))]

        from pytools import product
        normalization = 1/product(h-l for l, h in zip(self.lower, self.upper))

        def f(x):
            for i, l, h in compdata:
                if x < l or h < x:
                    return 0
            return normalization

        return f




# kv --------------------------------------------------------------------------
class KV(ParticleDistribution):
    def __init__(self, center, radii, emittances, next):
        """Construct a beam that is KV-distributed in (x,y)
        and uniform over an interval along z.

        @par radii: total (100%) radii
        @par emittances: total (100%) emittances
        """

        assert len(radii) == len(emittances)

        self.center = center
        self.radii = radii
        self.emittances = emittances
        self.next = next

    @property
    def rms_radii(self):
        return [r/2 for r in self.radii]

    @property
    def rms_emittances(self):
        return [eps/4 for eps in self.emittances]

    def count_axes(self):
        next_axes = self.next.count_axes()
        return (len(self.radii)+next_axes[0], 
                len(self.emittances)+next_axes[1],
                ) + next_axes[2:]

    def make_particle(self):
        """Return (position, velocity) for a random particle
        according to a Kapchinskij-Vladimirskij distribution.
        """
        from pytools import uniform_on_unit_sphere

        s = uniform_on_unit_sphere(len(self.radii) + len(self.emittances))
        x = [x_i*r_i for x_i, r_i in zip(s[:len(self.radii)], self.radii)] \
                + [self.
        # xp like xprime
        xp = [s_i/r_i*eps_i 
                for s_i, r_i, eps_i in 
                zip(s[len(self.radii):], self.radii, self.emittances)]

        one = sum(x_i**2/r_i**2 for x_i, r_i in zip(x, self.radii)) + \
                sum(xp_i**2*r_i**2/eps_i**2 
                for xp_i, r_i, epsi in zip(xp, self.radii, self.emittances))
        assert abs(one-1) < 1e-15

        z, vz, charge, mass = self.next.make_particle()

        # caution: these pluses are list extensions, not vector additions
        return ([xi+ci for xi, ci in zip(x, self.center)] + z, 
                [xp_i*la.norm(vz) for xp_i in xp] + vz, charge, mass)

    def mean(self):
        next_mean = self.next.mean()
        return (list(self.center) + next_mean[0],
                [0 for epsi in self.emittances] + next_mean[1]) + next_mean[2:]
        
    def get_rho_distrib(self):
        z_func = self.next.get_rho_distrib()
        z_slice = slice(start=len(self.radii), stop=None)
        my_slice = slice(0, len(self.center))

        n = len(self.radii)
        from math import pi
        from pyrticle._internal import gamma
        from pytools import product
        distr_vol = (2*pi)**(n/2) / (gamma(n/2)*n) * product(self.radii) * self.z_length
        normalization = 1/distr_vol

        def f(x):
            if la.norm((x[my_slice]-self.center)/self.radii) <= 1:
                return normalization*z_func(x[z_slice])
            else:
                return 0

        return f




class KVZIntervalBeam(KV):
    def __init__(self, units, total_charge, p_charge, p_mass,
            radii, emittances, beta, z_length, z_pos):
        KV.__init__(self, [0 for ri in radii], radii, emittances,
                JointParticleDistribution([
                    DeltaChargeMass(p_charge, p_mass),
                    UniformPos([z_pos-z_length/2, z_pos+z_length/2]),
                    DeltaVelocity([beta*units.VACUUM_LIGHT_SPEED]),
                    ])

        self.units = units
        self.total_charge = total_charge
        self.particle_charge = p_charge
        self.particle_mass = p_mass
        self.beta = beta
        self.z_length = z_length

    def get_total_space_charge_parameter(self):
        from math import pi

        # see http://en.wikipedia.org/wiki/Classical_electron_radius
        r0 = 1/(4*pi*self.units.EPSILON0)*( 
                (self.units.EL_CHARGE**2)
                /
                (self.units.EL_MASS*self.units.VACUUM_LIGHT_SPEED**2))

        lambda_ = self.total_charge /(self.z_length*self.units.EL_CHARGE)

        # factor of 2 here is uncertain
        # from S.Y.Lee, Accelerator Physics, p. 68
        # 2nd ed. 
        # (2.140), space charge term (2.136)

        gamma = (1-self.beta**2)**(-0.5)

        xi = 4*((lambda_ * r0) / (self.beta**2 * gamma**3))

        return xi

    def get_rms_space_charge_parameter(self):
        # by rms scaling analysis on the KV ODE
        return self.get_total_space_charge_parameter()/4

    def get_chargeless_rms_predictor(self, axis):
        return ChargelessKVRadiusPredictor(
                self.rms_radii[axis], self.rms_emittances[axis])

    def get_rms_predictor(self, axis):
        return KVRadiusPredictor(
                self.rms_radii[axis], self.rms_emittances[axis],
                xi=self.get_rms_space_charge_parameter())

    def get_total_predictor(self, axis):
        return KVRadiusPredictor(
                self.radii[axis], self.emittances[axis],
                xi=self.get_total_space_charge_parameter(unit))




# kv bonus stuff --------------------------------------------------------------
class ChargelessKVRadiusPredictor:
    def __init__(self, a0, eps):
        self.a0 = a0
        self.eps = eps

    def __call__(self, s):
        from math import sqrt
        return sqrt(self.a0**2+(self.eps/self.a0)**2 * s**2)




class KVRadiusPredictor(pyrticle.tools.ODEDefinedFunction):
    """Implement equation (1.74) in Alex Chao's book.

    See equation (1.65) for the definition of M{xi}.
    M{Q} is the number of electrons in the beam
    """
    def __init__(self, a0, eps, eB_2E=0, xi=0, dt=1e-4):
        pyrticle.tools.ODEDefinedFunction.__init__(self, 0, numpy.array([a0, 0]), 
                dt=dt*(a0**4/eps**2)**2)
        self.eps = eps
        self.xi = xi
        self.eB_2E = eB_2E

    def rhs(self, t, y):
        a = y[0]
        aprime = y[1]
        return numpy.array([
            aprime, 
            - self.eB_2E**2 * a
            + self.eps**2/a**3
            + self.xi/(2*a)
            ])

    def __call__(self, t):
        return pyrticle.tools.ODEDefinedFunction.__call__(self, t)[0]




class KVPredictedRadius(pytools.log.SimulationLogQuantity):
    def __init__(self, dt, beam_v, predictor, suffix, name=None):
        if name is None:
            name = "r%s_theory" % suffix

        pytools.log.SimulationLogQuantity.__init__(self, dt, name, "m", 
                "Theoretical RMS Beam Radius")

        self.beam_v = beam_v
        self.predictor = predictor
        self.t = 0

    def __call__(self):
        s = self.beam_v * self.t
        self.t += self.dt
        return self.predictor(s)




# gaussian --------------------------------------------------------------------
class GaussianPos(ParticleDistribution):
    def __init__(self, mean_x, sigma_x):
        self.mean_x = mean_x
        self.sigma_x = sigma_x

    def count_axes(self):
        return (len(self.mean_x), 0, 0, 0)

    def make_particle(self):
        return ([gauss(m, s) for m, s in zip(self.mean_x, self.sigma_x)],
                [],[],[])

    def mean(self):
        return (self.mean_x, [],[],[])

    def get_rho_distrib(self, discr):
        from math import exp, pi

        sigma_mat = numpy.diag(self.sigma_x**2)
        inv_sigma_mat = numpy.diag(self.sigma_x**(-2))

        from numpy import dot

        normalization = 1/((2*pi)**(len(x)/2) * la.det(sigma_mat)**0.5)

        def distrib(x):
            x0 = x-self.mean_x
            return normalization * exp(-0.5*dot(x0, dot(inv_sigma_mat, x0)))

        return distrib




class GaussianMomentum(ParticleDistribution):
    def __init__(self, mean_p, sigma_p, units):
        self.mean_p = mean_p
        self.sigma_p = sigma_p
        self.units = units

    def count_axes(self):
        return (0, len(self.mean_p), 0, 0)

    def make_particle(self):
        monentum = self.units_v_from_p(numpy.array(
                [gauss(m, s) for m, s in zip(self.mean_p, self.sigma_p)]))

        return ([], list(momentum), [], [])

    def mean(self):
        return ([None for m in self.mean_p], [],[],[])
