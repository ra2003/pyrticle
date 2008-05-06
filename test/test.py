from __future__ import division




import numpy
import numpy.linalg as la
import unittest




class TestPyrticle(unittest.TestCase):
    def test_ode_defined_function(self):
        from pyrticle.tools import ODEDefinedFunction

        class Sin(ODEDefinedFunction):
            def __init__(self):
                ODEDefinedFunction.__init__(self, 0, 
                        numpy.array([0,1]), 1/7*1e-2)

            def rhs(self, t, y):
                return numpy.array([y[1], -y[0]])

            def __call__(self, t):
                return ODEDefinedFunction.__call__(self, t)[0]

        from math import pi
        s = Sin()
        self.assert_(abs(s(-pi)) < 2e-3)
        self.assert_(abs(s(pi)) < 2e-3)
        self.assert_(abs(s(-pi/2)+1) < 2e-3)
    # -------------------------------------------------------------------------
    def test_kv_predictors(self):
        from pyrticle.distribution import \
                ChargelessKVRadiusPredictor, KVRadiusPredictor
        kv_env_exact = ChargelessKVRadiusPredictor(2.5e-3, 5e-6)
        kv_env_num = KVRadiusPredictor(2.5e-3, 5e-6)

        from hedge.tools import plot_1d
        steps = 50
        for i in range(steps):
            s = kv_env_num.dt/7*i
            
            a_exact = kv_env_exact(s)
            a_num = kv_env_num(s)
            self.assert_(abs(a_exact-a_num)/a_exact < 1e-3)
    # -------------------------------------------------------------------------
    def test_kv_with_no_charge(self):
        from random import seed
        seed(0)

        from pyrticle.units import SI
        units = SI()

        # discretization setup ----------------------------------------------------
        from hedge.element import TetrahedralElement
        from hedge.mesh import make_cylinder_mesh
        from hedge.discretization import Discretization

        tube_length = 100*units.MM
        mesh = make_cylinder_mesh(radius=25*units.MM, height=tube_length, periodic=True)

        discr = Discretization(mesh, TetrahedralElement(3))

        dt = discr.dt_factor(units.VACUUM_LIGHT_SPEED) / 2
        final_time = 1*units.M/units.VACUUM_LIGHT_SPEED
        nsteps = int(final_time/dt)+1
        dt = final_time/nsteps

        # particles setup ---------------------------------------------------------
        from pyrticle.cloud import ParticleCloud, FaceBasedElementFinder
        from pyrticle.reconstruction import ShapeFunctionReconstructor
        from pyrticle.pusher import MonomialParticlePusher

        cloud = ParticleCloud(discr, units, 
                ShapeFunctionReconstructor(),
                MonomialParticlePusher(),
                FaceBasedElementFinder(),
                3, 3, verbose_vis=False)

        nparticles = 10000
        cloud_charge = 1e-9 * units.C
        electrons_per_particle = cloud_charge/nparticles/units.EL_CHARGE

        el_energy = 5.2e6 * units.EV
        gamma = el_energy/units.EL_REST_ENERGY
        beta = (1-1/gamma**2)**0.5

        from pyrticle.distribution import KVZIntervalBeam
        beam = KVZIntervalBeam(units, 
                total_charge=0, 
                p_charge=0,
                p_mass=electrons_per_particle*units.EL_MASS,
                radii=2*[2.5*units.MM],
                emittances=2*[5 * units.MM * units.MRAD], 
                z_length=5*units.MM,
                z_pos=10*units.MM,
                beta=beta)
        
        cloud.add_particles(nparticles, beam.generate_particles())

        # diagnostics setup -------------------------------------------------------
        from pytools.log import LogManager
        from pyrticle.log import add_beam_quantities
        logmgr = LogManager()
        add_beam_quantities(logmgr, cloud, axis=0, beam_axis=2)

        from pyrticle.distribution import KVPredictedRadius
        logmgr.add_quantity(KVPredictedRadius(dt, 
            beam_v=beta*units.VACUUM_LIGHT_SPEED,
            predictor=beam.get_rms_predictor(axis=0),
            suffix="x_rms"))
        logmgr.add_quantity(KVPredictedRadius(dt, 
            beam_v=beta*units.VACUUM_LIGHT_SPEED,
            predictor=beam.get_total_predictor(axis=0),
            suffix="x_total"))

        # timestep loop -----------------------------------------------------------
        vel = cloud.velocities()
        from hedge.tools import join_fields
        def rhs(t, y):
            return join_fields([
                vel, 
                0*vel, 
                0, # drecon
                ])

        from hedge.timestep import RK4TimeStepper
        stepper = RK4TimeStepper()
        t = 0

        for step in xrange(nsteps):
            logmgr.tick()

            cloud = stepper(cloud, t, dt, rhs)
            cloud.upkeep()
            t += dt

        logmgr.tick()

        _, _, err_table = logmgr.get_expr_dataset("(rx_rms-rx_rms_theory)/rx_rms_theory")
        rel_max_rms_error = max(err for step, err in err_table)
        self.assert_(rel_max_rms_error < 0.01)
    # -------------------------------------------------------------------------
    def test_efield_vs_gauss_law(self):
        from hedge.element import TetrahedralElement
        from hedge.mesh import \
                make_box_mesh, \
                make_cylinder_mesh
        from math import sqrt, pi
        from pytools.arithmetic_container import \
                ArithmeticList, join_fields
        from hedge.operators import MaxwellOperator, DivergenceOperator
        from pyrticle.cloud import ParticleCloud
        from random import seed
        from pytools.stopwatch import Job

        from pyrticle.units import SI
        units = SI()

        seed(0)

        nparticles = 10000
        beam_radius = 2.5 * units.MM
        emittance = 5 * units.MM * units.MRAD
        final_time = 0.1*units.M/units.VACUUM_LIGHT_SPEED
        field_dump_interval = 1
        tube_length = 20*units.MM

        # discretization setup ----------------------------------------------------
        from pyrticle.geometry import make_cylinder_with_fine_core
        mesh = make_cylinder_with_fine_core(
                r=10*beam_radius, inner_r=1*beam_radius, 
                min_z=0, max_z=tube_length,
                max_volume_inner=10*units.MM**3,
                max_volume_outer=100*units.MM**3,
                radial_subdiv=10,
                )

        from hedge.discretization import Discretization
        discr = Discretization(mesh, TetrahedralElement(3))

        max_op = MaxwellOperator(discr, 
                epsilon=units.EPSILON0, 
                mu=units.MU0, 
                upwind_alpha=1)
        div_op = DivergenceOperator(discr)

        # particles setup ---------------------------------------------------------
        from pyrticle.cloud import ParticleCloud, FaceBasedElementFinder
        from pyrticle.reconstruction import ShapeFunctionReconstructor
        from pyrticle.pusher import MonomialParticlePusher

        cloud = ParticleCloud(discr, units, 
                ShapeFunctionReconstructor(),
                MonomialParticlePusher(),
                FaceBasedElementFinder(),
                3, 3, verbose_vis=False)

        cloud_charge = -1e-9 * units.C
        electrons_per_particle = abs(cloud_charge/nparticles/units.EL_CHARGE)

        el_energy = 10*units.EL_REST_ENERGY
        el_lorentz_gamma = el_energy/units.EL_REST_ENERGY
        beta = (1-1/el_lorentz_gamma**2)**0.5
        gamma = 1/sqrt(1-beta**2)

        from pyrticle.distribution import KVZIntervalBeam
        beam = KVZIntervalBeam(units, total_charge=cloud_charge,
                p_charge=cloud_charge/nparticles,
                p_mass=electrons_per_particle*units.EL_MASS,
                radii=2*[beam_radius],
                emittances=2*[5 * units.MM * units.MRAD], 
                z_length=tube_length,
                z_pos=tube_length/2,
                beta=beta)
        cloud.add_particles(nparticles, beam.generate_particles())

        # intial condition --------------------------------------------------------
        from pyrticle.cloud import guess_shape_bandwidth
        guess_shape_bandwidth(cloud, 2)

        from pyrticle.cloud import compute_initial_condition
        from hedge.parallel import SerialParallelizationContext
        fields = compute_initial_condition(SerialParallelizationContext(), 
                discr, cloud, max_op=max_op)

        # check against theory ----------------------------------------------------
        q_per_unit_z = cloud_charge/beam.z_length
        class TheoreticalEField():
            shape = (3,)

            def __call__(self, x):
                r = la.norm(x[:2])
                if r >= max(beam.radii):
                    xy_unit = x/r
                    xy_unit[2] = 0
                    return xy_unit*((q_per_unit_z)
                            /
                            (2*pi*r*max_op.epsilon))
                else:
                    return numpy.zeros((3,))

        def theory_indicator(x):
            r = la.norm(x[:2])
            if r >= max(beam.radii):
                return 1
            else:
                return 0

        from hedge.tools import join_fields, to_obj_array
        e_theory = to_obj_array(discr.interpolate_volume_function(TheoreticalEField()))
        theory_ind = discr.interpolate_volume_function(theory_indicator)

        restricted_e = join_fields(*[e_i * theory_ind for e_i in fields.e])

        def l2_error(field, true):
            from hedge.discretization import norm
            return norm(discr, field-true)/norm(discr, true)

        outer_l2 = l2_error(restricted_e, e_theory)
        self.assert_(outer_l2 < 0.08)

        if False:
            visf = vis.make_file("e_comparison")
            mesh_scalars, mesh_vectors = \
                    cloud.add_to_vis(vis, visf)
            vis.add_data(visf, [
                ("e", restricted_e), 
                ("e_theory", e_theory), 
                ]
                + mesh_vectors
                + mesh_scalars
                )
            visf.close()
    # -------------------------------------------------------------------------
    def test_with_static_fields(self):
        from pyrticle.units import SI

        units = SI()

        from hedge.element import TetrahedralElement
        from hedge.mesh import \
                make_box_mesh, \
                make_cylinder_mesh
        from hedge.discretization import Discretization

        # discretization setup ----------------------------------------------------
        radius = 1*units.M
        full_mesh = make_cylinder_mesh(radius=radius, height=2*radius, periodic=True,
                radial_subdivisions=30)

        from hedge.parallel import guess_parallelization_context

        pcon = guess_parallelization_context()

        if pcon.is_head_rank:
            mesh = pcon.distribute_mesh(full_mesh)
        else:
            mesh = pcon.receive_mesh()

        discr = pcon.make_discretization(mesh, TetrahedralElement(1))

        # particles setup ---------------------------------------------------------
        def get_setup(case):
            c = units.VACUUM_LIGHT_SPEED
            from static_field import LarmorScrew, EBParallel
            if case == "screw":
                return LarmorScrew(units, 
                        mass=units.EL_MASS, charge=units.EL_CHARGE, c=c,
                        vpar=c*0.8, vperp=c*0.1, bz=1e-3, 
                        nparticles=4)
            elif case == "epb":
                return EBParallel(units,
                        mass=units.EL_MASS, charge=units.EL_CHARGE, c=c,
                        ez=1e+5, bz=1e-3, radius=0.5*radius, nparticles=1)
            else:
                raise ValueError, "invalid test case"

        from pyrticle.pusher import \
                MonomialParticlePusher, \
                AverageParticlePusher

        from static_field import run_setup

        for pusher in [MonomialParticlePusher, AverageParticlePusher]:
            for case in ["screw", "epb"]:
                casename = "%s-%s" % (case, pusher.name.lower())
                run_setup(units, casename, get_setup(case), discr, pusher)



if __name__ == '__main__':
    unittest.main()