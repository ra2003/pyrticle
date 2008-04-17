"""Python interface for reconstructors"""

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




import pyrticle._internal as _internal
import pytools.log
import numpy
import numpy.linalg as la




class Reconstructor(object):
    def __init__(self):
        pass
    
    def initialize(self, cloud):
        self.cloud = cloud
        self.shape_function = None

    def set_shape_function(self, sf):
        self.shape_function = sf

    def add_instrumentation(self, mgr):
        pass

    def clear_particles(self):
        pass

    def reconstruct_hook(self):
        if self.shape_function is None:
            raise RuntimeError, "shape function never set"

    def rhs(self):
        return 0

    def add_rhs(self, rhs):
        return 0




class ShapeFunctionReconstructor(Reconstructor):
    name = "Shape"

    def set_shape_function(self, sf):
        Reconstructor.set_shape_function(self, sf)
        self.cloud.pic_algorithm.shape_function = sf





class NormalizedShapeFunctionReconstructor(Reconstructor):
    name = "NormShape"

    def initialize(self, cloud):
        Reconstructor.initialize(self, cloud)

        eg, = cloud.mesh_data.discr.element_groups
        ldis = eg.local_discretization

        cloud.pic_algorithm.setup_normalized_shape_reconstructor(
                ldis.mass_matrix())

    def add_instrumentation(self, mgr):
        Reconstructor.add_instrumentation(self, mgr)

        from pyrticle.log import StatsGathererLogQuantity
        mgr.add_quantity(StatsGathererLogQuantity(
            self.cloud.pic_algorithm.normalization_stats,
            "normshape_norm", "1", 
            "normalization constants applied during reconstruction"))

        mgr.add_quantity(StatsGathererLogQuantity(
            self.cloud.pic_algorithm.centroid_distance_stats,
            "normshape_centroid_dist", "m", 
            "distance of shape center from element centroid"))

        mgr.add_quantity(StatsGathererLogQuantity(
            self.cloud.pic_algorithm.el_per_particle_stats,
            "normshape_el_per_particle", "1", 
            "number of elements per particle"))

    def set_shape_function(self, sf):
        Reconstructor.set_shape_function(self, sf)
        self.cloud.pic_algorithm.shape_function = sf





# advective reconstruction ----------------------------------------------------
class ActiveAdvectiveElements(pytools.log.LogQuantity):
    def __init__(self, reconstructor, name="n_advec_elements"):
        pytools.log.LogQuantity.__init__(self, name, "1", "#active advective elements")
        self.reconstructor = reconstructor

    def __call__(self):
        return self.reconstructor.cloud.pic_algorithm.active_elements




class AdvectiveReconstructor(Reconstructor, _internal.NumberShiftListener):
    name = "Advective"

    def __init__(self, activation_threshold=1e-5, kill_threshold=1e-3, 
            filter_amp=None, filter_order=None, 
            upwind_alpha=1):
        Reconstructor.__init__(self)
        _internal.NumberShiftListener.__init__(self)

        from pyrticle.tools import NumberShiftMultiplexer
        self.rho_shift_signaller = NumberShiftMultiplexer()

        self.activation_threshold = activation_threshold
        self.kill_threshold = kill_threshold
        self.upwind_alpha = upwind_alpha

        self.shape_function = None

        self.filter_amp = filter_amp
        self.filter_order = filter_order

        if filter_amp is not None:
            from hedge.discretization import ExponentialFilterResponseFunction
            self.filter_response = ExponentialFilterResponseFunction(
                    filter_amp, filter_order)
        else:
            self.filter_response = None

        # instrumentation 
        from pytools.log import IntervalTimer, EventCounter
        self.element_activation_counter = EventCounter(
                "n_el_activations",
                "#Advective rec. elements activated this timestep")
        self.element_kill_counter = EventCounter(
                "n_el_kills",
                "#Advective rec. elements retired this timestep")
        self.advective_rhs_timer = IntervalTimer(
                "t_advective_rhs",
                "Time spent evaluating advective RHS")
        self.active_elements_log = ActiveAdvectiveElements(self)


    def initialize(self, cloud):
        Reconstructor.initialize(self, cloud)

        cloud.particle_number_shift_signaller.subscribe(self)

        discr = cloud.mesh_data.discr
        
        eg, = discr.element_groups
        (fg, fmm), = discr.face_groups
        ldis = eg.local_discretization

        from hedge.mesh import TAG_ALL
        bdry = discr._get_boundary(TAG_ALL)

        (bdry_fg, _), = bdry.face_groups_and_ldis

        if self.filter_response:
            from hedge.discretization import Filter
            filter = Filter(discr, self.filter_response)
            filter_mat, = filter.filter_matrices
        else:
            filter_mat = numpy.zeros((0,0))

        cloud.pic_algorithm.setup_advective_reconstructor(
                len(ldis.face_indices()),
                ldis.node_count(),
                ldis.mass_matrix(),
                ldis.inverse_mass_matrix(),
                filter_mat,
                fmm,
                fg,
                bdry_fg,
                self.activation_threshold,
                self.kill_threshold,
                self.upwind_alpha)

        for i, diffmat in enumerate(ldis.differentiation_matrices()):
            cloud.pic_algorithm.add_local_diff_matrix(i, diffmat)

        cloud.pic_algorithm.rho_dof_shift_listener = self.rho_shift_signaller

    def add_instrumentation(self, mgr):
        Reconstructor.add_instrumentation(self, mgr)

        mgr.add_quantity(self.element_activation_counter)
        mgr.add_quantity(self.element_kill_counter)
        mgr.add_quantity(self.advective_rhs_timer)
        mgr.add_quantity(self.active_elements_log)

        mgr.set_constant("el_activation_threshold", self.activation_threshold)
        mgr.set_constant("el_kill_threshold", self.kill_threshold)
        mgr.set_constant("adv_upwind_alpha", self.upwind_alpha)

        mgr.set_constant("filter_amp", self.filter_amp)
        mgr.set_constant("filter_amp", self.filter_order)

    def set_shape_function(self, sf):
        Reconstructor.set_shape_function(self, sf)

        self.cloud.pic_algorithm.clear_advective_particles()
        for pn in xrange(len(self.cloud)):
            self.cloud.pic_algorithm.add_advective_particle(sf, pn)

    def note_change_size(self, new_size):
        pic = self.cloud.pic_algorithm

        if (self.shape_function is not None 
                and new_size > pic.count_advective_particles()):
            for pn in range(pic.count_advective_particles(), new_size):
                pic.add_advective_particle(self.shape_function, pn)

    def clear_particles(self):
        Reconstructor.clear_particles(self)
        self.cloud.pic_algorithm.clear_advective_particles()

    def rhs(self):
        from pyrticle.tools import NumberShiftableVector
        self.advective_rhs_timer.start()
        result =  NumberShiftableVector(
                self.cloud.pic_algorithm.get_advective_particle_rhs(self.cloud.velocities()),
                multiplier=1,
                signaller=self.rho_shift_signaller
                )
        self.advective_rhs_timer.stop()
        self.element_activation_counter.transfer(
                self.cloud.pic_algorithm.element_activation_counter)
        self.element_kill_counter.transfer(
                self.cloud.pic_algorithm.element_kill_counter)

        return result

    def add_rhs(self, rhs):
        from pyrticle.tools import NumberShiftableVector
        self.cloud.pic_algorithm.apply_advective_particle_rhs(
                NumberShiftableVector.unwrap(rhs))




# grid reconstruction ---------------------------------------------------------
class SingleBrickGenerator:
    def __init__(self, overresolve=1.5):
        self.overresolve = overresolve

    def __call__(self, discr):
        from hedge.discretization import integral, ones_on_volume
        mesh_volume = integral(discr, ones_on_volume(discr))
        dx =  (mesh_volume/len(discr))**(1/discr.dimensions) \
                / self.overresolve

        mesh = discr.mesh
        bbox_min, bbox_max = mesh.bounding_box()
        bbox_size = bbox_max-bbox_min
        dims = numpy.asarray(bbox_size/dx, dtype=numpy.int32)
        stepwidths = bbox_size/dims
        yield stepwidths, bbox_min, dims




class GridReconstructor(Reconstructor):
    name = "Grid"

    def __init__(self, brick_generator=SingleBrickGenerator(), el_tolerance=0):
        self.brick_generator = brick_generator
        self.el_tolerance = el_tolerance

    def initialize(self, cloud):
        Reconstructor.initialize(self, cloud)

        discr = cloud.mesh_data.discr

        pic = self.cloud.pic_algorithm
        bricks = pic.bricks

        from pyrticle._internal import Brick
        for i, (stepwidths, origin, dims) in enumerate(
                self.brick_generator(discr)):
            bricks.append(Brick(i, pic.grid_node_count(),
                        stepwidths, origin, dims))

        self.prepare_with_pointwise_interpolation()

    def find_containing_brick(self, pt):
        for brk in self.cloud.pic_algorithm.bricks:
            if brk.bounding_box().contains(pt):
                return brk
        raise RuntimeError, "no containing brick found for point"

    def prepare_with_pointwise_interpolation(self):
        discr = self.cloud.mesh_data.discr
        pic = self.cloud.pic_algorithm
        bricks = pic.bricks

        pic.elements_on_grid.reserve(
                sum(len(eg.members) for eg in discr.element_groups))

        from pyrticle._internal import BrickIterator, ElementOnGrid, BoxFloat

        grid_node_count = pic.grid_node_count()

        # map brick numbers to [ (point, el_id, el_structured_point_index),...]
        # This is used to write out the C++ extra_points structure further
        # down.
        ep_brick_map = {}

        # Iterate over all elements
        for eg in discr.element_groups:
            ldis = eg.local_discretization

            for el in eg.members:
                eog = ElementOnGrid()

                el_bbox = BoxFloat(*el.bounding_box(discr.mesh.points))

                # enlarge the element bounding box by the mapped tolerance
                my_tolerance = self.el_tolerance * la.norm(el.map.matrix, 2)
                el_bbox.lower -= my_tolerance
                el_bbox.upper += my_tolerance

                # For each element, find all structured points inside the element.
                for brk in bricks:
                    brk_and_el = brk.bounding_box().intersect(el_bbox)

                    if brk_and_el.is_empty():
                        continue

                    points = []
                    for coord in BrickIterator(brk, brk.index_range(brk_and_el)):
                        point = brk.point(coord)
                        if pic.mesh_data.is_in_element(
                                el.id, point, self.el_tolerance):
                            points.append(point)
                            grid_node_index = brk.index(coord)
                            assert grid_node_index < grid_node_count
                            eog.grid_nodes.append(grid_node_index)

                node_count = ldis.node_count()
                if len(points) < node_count:
                    raise RuntimeError(
                            "element has too few structured grid points "
                            "(element #%d, #nodes=%d #sgridpt=%d)"
                            % (el.id, node_count, len(points)))

                # If the structured Vandermonde matrix is singular,
                # add "extra points" to prevent that.
                ep_count = 0
                while True:
                    from hedge.polynomial import generic_vandermonde
                    structured_vdm = generic_vandermonde(
                            [el.inverse_map(x) for x in points], 
                            ldis.basis_functions())

                    u, s, vt = la.svd(structured_vdm)
                    thresh = (numpy.finfo(float).eps
                            * max(structured_vdm.shape) * s[0])
                    zero_indices = [i for i, si in enumerate(s)
                        if abs(si) < thresh]

                    if not zero_indices:
                        break

                    ep_count += len(zero_indices)
                    if ep_count > 5:
                        raise RuntimeError(
                                "rec_grid: could not regularize structured "
                                "vandermonde matrix")

                    for zi in zero_indices:
                        # Getting here means that a mode
                        # maps to zero on the structured grid.
                        # Find it.
                        zeroed_mode = numpy.dot(
                                ldis.vandermonde(), vt[zi])

                        # Then, find the point in that mode with
                        # the highest absolute value.
                        from pytools import argmax
                        max_node_idx = argmax(abs(xi) for xi in zeroed_mode)
                        start, stop = discr.find_el_range(el.id)

                        new_point = discr.nodes[start+max_node_idx]

                        ep_brick_map.setdefault(
                                self.find_containing_brick(new_point).number,
                                []).append(
                                        (new_point, el.id, len(points)))

                        points.append(new_point)

                        # the final grid_node_number at which this point
                        # will end up is as yet unknown. insert a
                        # placeholder
                        eog.grid_nodes.append(0)

                if ep_count:
                    print "element %d #nodes=%d sgridpt=%d, extra=%d" % (
                            el.id, node_count, len(points), ep_count)
                else:
                    print "element %d #nodes=%d sgridpt=%d" % (
                            el.id, node_count, len(points))

                # compute the pseudoinverse of the structured
                # Vandermonde matrix
                inv_s_diag = numpy.zeros(
                        (node_count, len(points)), 
                        dtype=float)
                inv_s_diag[:len(s),:len(s)] = numpy.diag(1/s)

                svdm_pinv = numpy.dot(
                        numpy.dot(vt.T, inv_s_diag),
                        u.T)

                # check that it's reasonable
                pinv_resid = la.norm(
                    numpy.dot(svdm_pinv, structured_vdm)
                    - numpy.eye(node_count))

                if pinv_resid > 1e-8:
                    from warnings import warn
                    warn("rec_grid: bad pseudoinv precision, element=%d, "
                            "#nodes=%d, #sgridpts=%d, resid=%.5g centroid=%s"
                        % (el.id, node_count, len(points), pinv_resid,
                                el.centroid(discr.mesh.points)))

                # compose interpolation matrix
                eog.interpolation_matrix = numpy.asarray(
                        numpy.dot(ldis.vandermonde(), svdm_pinv),
                        order="F")

                pic.elements_on_grid.append(eog)

        # fill in the extra points
        ep_brick_starts = [0]
        extra_points = []
        
        for brk in bricks:
            for pt, el_id, struc_idx in ep_brick_map.get(brk.number, []):
                # replace zero placeholder from above
                pic.elements_on_grid[el_id].grid_nodes[struc_idx] = \
                        grid_node_count + len(extra_points)
                extra_points.append(pt)

            ep_brick_starts.append(len(extra_points))


        pic.first_extra_point = grid_node_count
        pic.extra_point_brick_starts.extend(ep_brick_starts)
        pic.extra_points = numpy.array(extra_points)

    def set_shape_function(self, sf):
        Reconstructor.set_shape_function(self, sf)
        self.cloud.pic_algorithm.shape_function = sf

    def write_grid_quantities(self, silo, quantities):
        dims = self.cloud.dimensions_mesh
        vdims = self.cloud.dimensions_velocity
        pic = self.cloud.pic_algorithm

        for i_brick, brick in enumerate(pic.bricks):
            coords = [
                numpy.arange(
                    brick.origin[axis] + brick.stepwidths[axis]/2, 
                    brick.origin[axis] 
                    + brick.dimensions[axis] * brick.stepwidths[axis], 
                    brick.stepwidths[axis])
                for axis in xrange(dims)]
            for axis in xrange(dims):
                assert len(coords[axis]) == brick.dimensions[axis]

            mname = "structmesh%d" % i_brick
            silo.put_quadmesh(mname, coords)

            from pylo import DB_NODECENT

            # get rid of array scalars
            brick_dims = [int(x) for x in brick.dimensions] 

            for quant in quantities:
                if quant == "rho":
                    vname = "rho_struct%d" % i_brick

                    silo.put_quadvar1(vname, mname, 
                            pic.get_grid_rho(),
                            brick_dims, DB_NODECENT)
                elif quant == "j":
                    vname = "j_struct%d" % i_brick

                    vnames = [
                        "%s_coord%d" % (vname, axis) 
                        for axis in range(vdims)]

                    from pytools import product
                    j_grid = numpy.reshape(
                            pic.get_grid_j(self.cloud.velocities()),
                            (product(brick_dims), vdims))

                    j_grid_compwise = numpy.asarray(j_grid.T, order="C")
                    
                    silo.put_quadvar(vname, mname, vnames,
                            j_grid_compwise,
                            brick_dims, DB_NODECENT)

