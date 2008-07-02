// Pyrticle - Particle in Cell in Python
// Python wrapper for reconstruction bits
// Copyright (C) 2007 Andreas Kloeckner
// 
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
// 
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
// 
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.




#ifndef _AYYTYAH_PYRTICLE_WRAP_RECONSTRUCTOR_HPP_INCLUDED
#define _AYYTYAH_PYRTICLE_WRAP_RECONSTRUCTOR_HPP_INCLUDED




#include "wrap_helpers.hpp"
#include "rec_shape.hpp"
#include "rec_normshape.hpp"
#include "rec_advective.hpp"
#include "rec_grid.hpp"
#include "rec_grid_find.hpp"




namespace pyrticle
{
  template <class Wrapper, class PIC>
  void expose_typed_reconstructor(Wrapper &wrp, 
      shape_function_reconstructor::type<PIC> *)
  { 
    typedef shape_function_reconstructor::type<PIC> cl;
    wrp
      .DEF_RW_MEMBER(shape_function)

      .DEF_SIMPLE_METHOD(reconstruct_densities)
      .DEF_SIMPLE_METHOD(reconstruct_rho)
      .DEF_SIMPLE_METHOD(reconstruct_j)
      ;
  }




  template <class Wrapper, class PIC>
  void expose_typed_reconstructor(Wrapper &wrp, 
      normalized_shape_function_reconstructor::type<PIC> *)
  { 
    typedef normalized_shape_function_reconstructor::type<PIC> cl;
    wrp
      .DEF_RO_MEMBER(normalization_stats)
      .DEF_RO_MEMBER(centroid_distance_stats)
      .DEF_RO_MEMBER(el_per_particle_stats)
      .DEF_SIMPLE_METHOD(setup_normalized_shape_reconstructor)

      .DEF_RW_MEMBER(shape_function)

      .DEF_SIMPLE_METHOD(reconstruct_densities)
      .DEF_SIMPLE_METHOD(reconstruct_rho)
      .DEF_SIMPLE_METHOD(reconstruct_j)
      ;
  }




  template <class Wrapper, class PIC>
  void expose_typed_reconstructor(Wrapper &wrp, 
      typename advective_reconstructor::type<PIC> *)
  { 
    using boost::python::arg;

    typedef typename advective_reconstructor::template type<PIC> cl;
    wrp
      .DEF_SIMPLE_METHOD(setup_advective_reconstructor)
      .DEF_RW_MEMBER(rho_dof_shift_listener)

      .DEF_RO_MEMBER(active_elements)

      .DEF_RO_MEMBER(element_activation_counter)
      .DEF_RO_MEMBER(element_kill_counter)

      .DEF_SIMPLE_METHOD(add_local_diff_matrix)
      .DEF_SIMPLE_METHOD(count_advective_particles)
      .DEF_SIMPLE_METHOD(add_advective_particle)
      .DEF_SIMPLE_METHOD(clear_advective_particles)
      .DEF_SIMPLE_METHOD(get_debug_quantity_on_mesh)
      .DEF_SIMPLE_METHOD(get_advective_particle_rhs)
      .DEF_SIMPLE_METHOD(apply_advective_particle_rhs)

      .DEF_SIMPLE_METHOD(reconstruct_densities)
      .DEF_SIMPLE_METHOD(reconstruct_rho)
      .DEF_SIMPLE_METHOD(reconstruct_j)

      .DEF_SIMPLE_METHOD(perform_reconstructor_upkeep)
      ;
  }




  template <class PIC>
  py_vector get_extra_points(const PIC &pic)
  { return pic.m_extra_points; }

  template <class PIC>
  void set_extra_points(PIC &pic, py_vector v)
  { pic.m_extra_points = v; }

  template <class Wrapper, class PIC, class Brick>
  void expose_typed_reconstructor_inner(Wrapper &wrp, 
      typename grid_reconstructor<Brick>::template type<PIC> *)
  { 
    typedef typename grid_reconstructor<Brick>::template type<PIC> cl;
    wrp
      .DEF_RW_MEMBER(shape_function)
      .DEF_RW_MEMBER(bricks)
      .DEF_RW_MEMBER(elements_on_grid)

      .DEF_RW_MEMBER(first_extra_point)
      // PyUblas member-in-base-class issue: wrap by hand
      .add_property("extra_points", get_extra_points<PIC>, set_extra_points<PIC>)
      .DEF_RW_MEMBER(extra_point_brick_starts)

      .DEF_RW_MEMBER(average_groups)
      .DEF_RW_MEMBER(average_group_starts)

      .DEF_SIMPLE_METHOD(find_points_in_element)
      .DEF_SIMPLE_METHOD(grid_node_count)

      .DEF_SIMPLE_METHOD(remap_grid_to_mesh)
      .DEF_SIMPLE_METHOD(remap_residual)

      .DEF_SIMPLE_METHOD(reconstruct_grid_densities)
      .DEF_SIMPLE_METHOD(reconstruct_grid_j)
      .DEF_SIMPLE_METHOD(reconstruct_grid_rho)
      ;
  }
  template <class Wrapper, class PIC>
  void expose_typed_reconstructor(Wrapper &wrp, 
      typename grid_reconstructor<jiggly_brick>::template type<PIC> *r)
  { 
    expose_typed_reconstructor_inner<Wrapper, PIC, jiggly_brick>(wrp, r);
  }




  template <class Wrapper, class PIC>
  void expose_typed_reconstructor(Wrapper &wrp, 
      typename grid_find_reconstructor::type<PIC> *)
  { 
    typedef grid_find_reconstructor::type<PIC> cl;
    wrp
      .DEF_RW_MEMBER(shape_function)
      .DEF_RW_MEMBER(bricks)
      .DEF_RW_MEMBER(node_number_list_starts)
      .DEF_RW_MEMBER(node_number_lists)

      .DEF_SIMPLE_METHOD(grid_node_count)

      .DEF_SIMPLE_METHOD(reconstruct_densities)
      .DEF_SIMPLE_METHOD(reconstruct_j)
      .DEF_SIMPLE_METHOD(reconstruct_rho)
      ;
  }
}




#endif
