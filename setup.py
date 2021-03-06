#!/usr/bin/env python
# -*- coding: latin-1 -*-

# Hedge - the Hybrid'n'Easy DG Environment
# Copyright (C) 2007 Andreas Kloeckner
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


def get_config_schema():
    from aksetup_helper import ConfigSchema, \
            IncludeDir, LibraryDir, Libraries, BoostLibraries, \
            StringListOption, make_boost_base_options

    return ConfigSchema(make_boost_base_options() + [
        BoostLibraries("python"),

        IncludeDir("BOOST_BINDINGS", []),

        LibraryDir("BLAS", []),
        Libraries("BLAS", ["blas"]),
        LibraryDir("LAPACK", []),
        Libraries("LAPACK", ["lapack"]),

        StringListOption("CXXFLAGS", [],
            help="Any extra C++ compiler options to include"),
        ])


def main():
    from aksetup_helper import hack_distutils, get_config, setup, \
            HedgeExtension

    hack_distutils()
    conf = get_config(get_config_schema())

    LIBRARY_DIRS = conf["BOOST_LIB_DIR"]
    LIBRARIES = conf["BOOST_PYTHON_LIBNAME"]

    EXTRA_DEFINES = {
            "PYUBLAS_HAVE_BOOST_BINDINGS": 1,
            }
    EXTRA_INCLUDE_DIRS = []
    EXTRA_LIBRARY_DIRS = []
    EXTRA_LIBRARIES = []

    INCLUDE_DIRS = ["src/cpp"] \
            + conf["BOOST_BINDINGS_INC_DIR"] \
            + conf["BOOST_INC_DIR"]

    conf["BLAS_INC_DIR"] = []
    conf["LAPACK_INC_DIR"] = []
    conf["USE_BLAS"] = True
    conf["USE_LAPACK"] = True

    def handle_component(comp):
        if conf["USE_"+comp]:
            EXTRA_DEFINES["USE_"+comp] = 1
            EXTRA_INCLUDE_DIRS.extend(conf[comp+"_INC_DIR"])
            EXTRA_LIBRARY_DIRS.extend(conf[comp+"_LIB_DIR"])
            EXTRA_LIBRARIES.extend(conf[comp+"_LIBNAME"])

    handle_component("LAPACK")
    handle_component("BLAS")

    setup(
            name="pyrticle",
            version="0.90",
            description="A high-order PIC code using Hedge",
            author=u"Andreas Kloeckner",
            author_email="inform@tiker.net",
            license="GPLv3",
            url="http://mathema.tician.de/software/pyrticle",

            scripts=["bin/pyrticle"],

            packages=["pyrticle", "pyrticle.deposition"],
            ext_package="pyrticle",
            ext_modules=[
                HedgeExtension("_internal",
                    [
                        "src/cpp/tools.cpp",
                        "src/wrapper/wrap_tools.cpp",
                        "src/wrapper/wrap_grid.cpp",
                        "src/wrapper/wrap_meshdata.cpp",
                        "src/wrapper/wrap_pic.cpp",
                        "src/wrapper/wrap_pusher.cpp",
                        "src/wrapper/wrap_depositor.cpp",
                        "src/wrapper/wrap_main.cpp",
                        ],
                    include_dirs=INCLUDE_DIRS + EXTRA_INCLUDE_DIRS,
                    library_dirs=LIBRARY_DIRS + EXTRA_LIBRARY_DIRS,
                    libraries=LIBRARIES + EXTRA_LIBRARIES,
                    extra_compile_args=conf["CXXFLAGS"],
                    define_macros=list(EXTRA_DEFINES.iteritems()),
                    )]
                )


if __name__ == '__main__':
    main()
