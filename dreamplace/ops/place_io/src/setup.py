##
# @file   setup.py
# @author Yibo Lin
# @date   Jun 2018
#

import os
import sys 
from setuptools import setup
from torch.utils.cpp_extension import BuildExtension, CppExtension

limbo_dir = "${LIMBO_DIR}"

include_dirs = [os.path.join(os.path.abspath(limbo_dir), 'include'), '${Boost_INCLUDE_DIRS}', '${ZLIB_INCLUDE_DIRS}']
lib_dirs = [os.path.join(os.path.abspath(limbo_dir), 'lib'), '${Boost_LIBRARY_DIRS}', os.path.dirname('${ZLIB_LIBRARIES}')]
libs = ['lefparseradapt', 'defparseradapt', 'verilogparser', 'gdsparser', 'bookshelfparser', 'programoptions', 'boost_system', 'boost_timer', 'boost_chrono', 'boost_iostreams', 'z'] 


def add_prefix(filename):
    return os.path.join('${CMAKE_CURRENT_SOURCE_DIR}/src', filename)

setup(
        name='place_io',
        ext_modules=[
            CppExtension('place_io_cpp', 
                [
                    add_prefix('place_io.cpp'),  
                    add_prefix('BenchMetrics.cpp'),  
                    add_prefix('BinMap.cpp'),  
                    add_prefix('Enums.cpp'),  
                    add_prefix('Msg.cpp'),  
                    add_prefix('Net.cpp'),  
                    add_prefix('Node.cpp'),  
                    add_prefix('Params.cpp'),  
                    add_prefix('PlaceDB.cpp'),  
                    add_prefix('DefWriter.cpp'),
                    add_prefix('BookshelfWriter.cpp')
                    ],
                include_dirs=include_dirs, 
                library_dirs=lib_dirs,
                libraries=libs,
                extra_compile_args={
                    'cxx': ['-fvisibility=hidden', '-D_GLIBCXX_USE_CXX11_ABI=0'], 
                    }
                ),
            ],
        cmdclass={
            'build_ext': BuildExtension
            })
