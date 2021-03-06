import random as _random
_random.seed(0)
import numpy.random as _numpyrandom
_numpyrandom.seed(1)

pusher = PushMonomial()
#depositor = DepGrid(
        #el_tolerance=0.1,
        #method="simplex_reduce",
        #jiggle_radius=0.0)
#depositor = DepAdv()
#depositor = DepShape()
depositor = DepGridFind()

debug.remove("shape_bw")
debug.add("vis_files")

dimensions_pos = 2
dimensions_velocity = 2

beam_axis = 0
beam_diag_axis = 1
tube_length = 2

shape_bandwidth = "guess"

_cloud_charge = 10e-9 * units.C
nparticles = 0
element_order = 3
final_time = 10*units.M/units.VACUUM_LIGHT_SPEED()
if nparticles:
    _electrons_per_particle = abs(_cloud_charge/nparticles/units.EL_CHARGE)
else:
    _electrons_per_particle = 1

def _make_a6():
    import sys, os
    sys.path.append(os.path.join(os.getcwd(), "mesh"))

    from magnetron import A6Triangulator as _A6Triangulator
    return _A6Triangulator()

_a6 = _make_a6()

def _make_mesh():
    tri_out = _a6.make_triangulation(5e-6)

    from hedge.mesh import MeshPyFaceMarkerLookup
    fmlookup = MeshPyFaceMarkerLookup(tri_out)

    marker2tags = {
            _a6.anode_marker: ["anode"],
            _a6.cathode_marker: ["cathode"],
            _a6.open_marker: ["open"],
            }

    def boundary_tagger(fvi, el, fn, points):
        return marker2tags[fmlookup(fvi)]

    from hedge.mesh import make_conformal_mesh

    return make_conformal_mesh(
            tri_out.points,
            tri_out.elements,
            boundary_tagger)

mesh = _make_mesh()

def _make_potential():
    from magnetron import A6Triangulator

    def pot(x, el):
        if la.norm(x) > (_a6.radius_cathode+_a6.radius_anode)/2:
            return 0
        else:
            return 500e3*units.V

    from hedge.data import GivenFunction
    return GivenFunction(pot)

potential_bc = _make_potential()

_c0 = units.VACUUM_LIGHT_SPEED()

_mean_v = numpy.array([_c0*0.9,0])
_sigma_v = numpy.array([_c0*0.9*1e-3, _c0*1e-5])

_mean_beta = _mean_v/units.VACUUM_LIGHT_SPEED()
_gamma = units.gamma_from_v(_mean_v)
_pmass = _electrons_per_particle*units.EL_MASS
_mean_p = _gamma*_pmass*_mean_v

distribution = pyrticle.distribution.JointParticleDistribution([
    pyrticle.distribution.GaussianPos([0.0,0.0], [0.01, 0.01]),
    pyrticle.distribution.GaussianMomentum(
        #_mean_p, _sigma_v*_gamma*_pmass, 
        0*_mean_p, 1e-10*_sigma_v*_gamma*_pmass, 
        units,
        pyrticle.distribution.DeltaChargeMass(
            _electrons_per_particle * units.EL_CHARGE,
            _pmass))
    ])

vis_interval = 10

def hook_startup(runner):
    # setup forcing b field
    b = 0.72 * units.T
    h = b/runner.maxwell_op.mu

    def h_func(x, el):
        return h

    e, _ = runner.maxwell_op.split_eh(runner.fields)
    runner.fields = runner.maxwell_op.assemble_eh(
            e=e,
            h=runner.discr.interpolate_volume_function(h_func))

def _disabled_hook_startup(runner):
    # write out e and b field for Martin
    def pad_with_zeros(l, desired_length=6):
        while len(l) < desired_length:
            l.append(0)
        return l

    points = [
            [float(x) for x in line.split()]
            for line in open("xyBary.txt").readlines()[1:]]

    outf = open("e_field_values.dat", "w")
    for pt in points:
        pt_values = runner.discr.evaluate_at_point(
                runner.fields.e, numpy.array(pt)/100)
        outf.write(" ".join(repr(ei)
            for ei in pad_with_zeros(list(pt_values))))
        #outf.write(" ".join(repr(ei)
            #for ei in list(pt)+list(pt_values)))
        outf.write("\n")

if isinstance(depositor, DepGrid):
    def hook_visualize(runner, vis, visf, observer):
        meth = runner.method
        dep = meth.depositor
        state = observer.state

        dep.visualize_grid_quantities(visf, [
                ("rho_grid", dep.deposit_grid_rho(state)),
                ("j_grid", dep.deposit_grid_j(state, meth.velocities(state))),
                ("ones_resid", dep.remap_residual(dep.ones_on_grid())),
                ("rho_resid", dep.remap_residual(dep.deposit_grid_rho(state))),
                ("usecount", dep.grid_usecount()),
                ])

def hook_after_step(runner, observer):
    # space-charge limited emission at cathode

    bdry = runner.discr.get_boundary("cathode")

    cathode_normals = runner.discr.boundary_normals("cathode")
    e_fld, _ = runner.maxwell_op.split_eh(runner.fields)
    cathode_e = numpy.array(list(runner.discr.boundarize_volume_field(
            e_fld, "cathode")))

    macro_particle_factor = 1e10
    
    def generate_particles():
        for e, pt, normal in zip(cathode_e.T, bdry.nodes, cathode_normals.T):
            if numpy.dot(e, normal) > 1e3:

                tangent = numpy.array([normal[1], -normal[0]])

                part_pt = (pt + (normal*-1e-5
                            + tangent*numpy.random.uniform(-0.03, 0.03))
                            *(_a6.radius_anode-_a6.radius_cathode))

                yield (part_pt,
                        runner.maxwell_op.c*0.02*-normal,
                        -macro_particle_factor*units.EL_CHARGE,
                        macro_particle_factor*units.EL_MASS,
                        )

    runner.method.add_particles(observer.state, generate_particles())
