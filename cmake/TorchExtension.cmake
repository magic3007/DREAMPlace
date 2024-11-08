# @file TorchExtension.cmake
# @author Zizheng Guo
# @brief Use CMake to compile PyTorch extensions

# Activate new FindPython mode, specified in pybind11Config.cmake.in...
# This one is recommended from CMake 3.12+.
# It should try to find the Python associated with the environment variable.
find_package(Python COMPONENTS Interpreter Development)
add_subdirectory(thirdparty/pybind11)

execute_process(COMMAND ${Python_EXECUTABLE} -c
  "import torch; print(torch.__path__[0]); print(int(torch.version.cuda is not None)); print(int(torch.version.hip is not None)); print(torch.__version__);"
  OUTPUT_VARIABLE TORCH_OUTPUT OUTPUT_STRIP_TRAILING_WHITESPACE)
string(REPLACE "\n" ";" TORCH_OUTPUT_LIST ${TORCH_OUTPUT})
list(GET TORCH_OUTPUT_LIST 0 TORCH_INSTALL_PREFIX)
list(GET TORCH_OUTPUT_LIST 1 TORCH_ENABLE_CUDA_BACKEND)
list(GET TORCH_OUTPUT_LIST 2 TORCH_ENABLE_HIP_BACKEND)
list(GET TORCH_OUTPUT_LIST 3 TORCH_VERSION)
string(REPLACE "." ";" TORCH_VERSION_LIST ${TORCH_VERSION})
list(GET TORCH_VERSION_LIST 0 TORCH_VERSION_MAJOR)
list(GET TORCH_VERSION_LIST 1 TORCH_VERSION_MINOR)

message(STATUS TORCH_INSTALL_PREFIX=${TORCH_INSTALL_PREFIX})
message(STATUS TORCH_VERSION=${TORCH_VERSION_MAJOR}.${TORCH_VERSION_MINOR})

if ("${TORCH_VERSION_MAJOR}.${TORCH_VERSION_MINOR}" VERSION_LESS 1.6)
  message(SEND_ERROR "require PyTorch version >=1.6")
#elseif ("${TORCH_VERSION_MAJOR}.${TORCH_VERSION_MINOR}" VERSION_GREATER_EQUAL 1.8)
#  message(SEND_ERROR "require PyTorch version < 1.8")
endif()

if (TORCH_ENABLE_CUDA_BACKEND)
  find_package(CUDA 9.0)
  if (NOT CUDA_FOUND)
    set(TORCH_ENABLE_CUDA_BACKEND 0 CACHE BOOL "Whether enable CUDA" FORCE)
  endif(NOT CUDA_FOUND)
endif()

if (TORCH_ENABLE_HIP_BACKEND)
  include("${CMAKE_CURRENT_LIST_DIR}/public/utils.cmake")
  include("${CMAKE_CURRENT_LIST_DIR}/public/LoadHIP.cmake")
  if (NOT HIP_FOUND)
    set(TORCH_ENABLE_HIP_BACKEND 0 CACHE BOOL "Whether enable HIP" FORCE)
  endif(NOT HIP_FOUND)
endif()

if (TORCH_ENABLE_CUDA_BACKEND OR TORCH_ENABLE_HIP_BACKEND)
  set(TORCH_ENABLE_CUDA TRUE CACHE BOOL "Whether CUDA or HIP is enabled" FORCE)
else()
  set(TORCH_ENABLE_CUDA FALSE CACHE BOOL "Whether CUDA or HIP is enabled" FORCE)
endif()

message(STATUS CUDA_FOUND=${CUDA_FOUND})
message(STATUS HIP_FOUND=${HIP_FOUND})
message(STATUS TORCH_ENABLE_CUDA_BACKEND=${TORCH_ENABLE_CUDA_BACKEND})
message(STATUS TORCH_ENABLE_HIP_BACKEND=${TORCH_ENABLE_HIP_BACKEND})
message(STATUS TORCH_ENABLE_CUDA=${TORCH_ENABLE_CUDA})

add_library(torch STATIC IMPORTED)
find_library(TORCH_PYTHON_LIBRARY torch_python PATHS "${TORCH_INSTALL_PREFIX}/lib" REQUIRED)
find_library(TORCH_LIBRARY torch PATHS "${TORCH_INSTALL_PREFIX}/lib" REQUIRED)
find_library(C10_LIBRARY c10 PATHS "${TORCH_INSTALL_PREFIX}/lib" REQUIRED)
if (TORCH_ENABLE_CUDA_BACKEND)
  find_library(C10_CUDA_LIBRARY c10_cuda PATHS "${TORCH_INSTALL_PREFIX}/lib" REQUIRED)
elseif (TORCH_ENABLE_HIP_BACKEND)
  find_library(C10_HIP_LIBRARY c10_hip PATHS "${TORCH_INSTALL_PREFIX}/lib" REQUIRED)
endif()
find_library(TORCH_CPU_LIBRARY torch_cpu PATHS "${TORCH_INSTALL_PREFIX}/lib" REQUIRED)
if (TORCH_ENABLE_CUDA_BACKEND)
  find_library(TORCH_CUDA_LIBRARY torch_cuda PATHS "${TORCH_INSTALL_PREFIX}/lib" REQUIRED)
elseif (TORCH_ENABLE_HIP_BACKEND)
  find_library(TORCH_HIP_LIBRARY torch_hip PATHS "${TORCH_INSTALL_PREFIX}/lib" REQUIRED)
endif()

if (EXISTS ${TORCH_INSTALL_PREFIX}/include)
  # torch version 1.4+
  set(TORCH_HEADER_PREFIX ${TORCH_INSTALL_PREFIX}/include)
elseif (EXISTS ${TORCH_INSTALL_PREFIX}/lib/include)
  # torch version 1.0
  set(TORCH_HEADER_PREFIX ${TORCH_INSTALL_PREFIX}/lib/include)
endif()
set(TORCH_INCLUDE_DIRS
  ${TORCH_HEADER_PREFIX}
  ${TORCH_HEADER_PREFIX}/torch/csrc/api/include)

set(LINK_LIBS ${C10_LIBRARY} ${TORCH_CPU_LIBRARY})
if (TORCH_ENABLE_CUDA_BACKEND)
  set(LINK_LIBS ${LINK_LIBS}
    ${C10_CUDA_LIBRARY}
    ${TORCH_CUDA_LIBRARY})
elseif (TORCH_ENABLE_HIP_BACKEND)
  set(LINK_LIBS ${LINK_LIBS}
    ${C10_HIP_LIBRARY}
    ${TORCH_HIP_LIBRARY})
endif()

set_target_properties(torch PROPERTIES
  IMPORTED_LOCATION "${TORCH_LIBRARY}"
  INTERFACE_INCLUDE_DIRECTORIES "${TORCH_INCLUDE_DIRS}"
  INTERFACE_LINK_LIBRARIES "${LINK_LIBS}"
  INTERFACE_COMPILE_OPTIONS "-D_GLIBCXX_USE_CXX11_ABI=${CMAKE_CXX_ABI}"
  )

# CXX only
function(add_torch_extension target_name)
  set(multiValueArgs EXTRA_INCLUDE_DIRS EXTRA_LINK_LIBRARIES EXTRA_DEFINITIONS)
  cmake_parse_arguments(ARG "" "" "${multiValueArgs}" ${ARGN})
  if (TORCH_ENABLE_CUDA_BACKEND)
    cuda_add_library(${target_name} STATIC ${ARG_UNPARSED_ARGUMENTS})
  elseif (TORCH_ENABLE_HIP_BACKEND)
    hip_add_library(${target_name} STATIC ${ARG_UNPARSED_ARGUMENTS})
  else()
    # remove cuda files
    list(FILTER ARG_UNPARSED_ARGUMENTS EXCLUDE REGEX ".*cu$")
    list(FILTER ARG_UNPARSED_ARGUMENTS EXCLUDE REGEX ".*cuh$")
    add_library(${target_name} STATIC ${ARG_UNPARSED_ARGUMENTS})
  endif()
  target_include_directories(${target_name} PRIVATE ${ARG_EXTRA_INCLUDE_DIRS})
  target_link_libraries(${target_name} ${ARG_EXTRA_LINK_LIBRARIES} torch pybind11::module)
  target_compile_definitions(${target_name} PRIVATE
    TORCH_EXTENSION_NAME=${target_name}
    TORCH_VERSION_MAJOR=${TORCH_VERSION_MAJOR}
    TORCH_VERSION_MINOR=${TORCH_VERSION_MINOR}
    ENABLE_CUDA=${TORCH_ENABLE_CUDA_BACKEND}
    ${ARG_EXTRA_DEFINITIONS})
  set_target_properties(${target_name} PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    CXX_VISIBILITY_PRESET "hidden"
    CUDA_VISIBILITY_PRESET "hidden"
    )
endfunction()

function(add_pytorch_extension target_name)
  set(multiValueArgs EXTRA_INCLUDE_DIRS EXTRA_LINK_LIBRARIES EXTRA_DEFINITIONS)
  cmake_parse_arguments(ARG "" "" "${multiValueArgs}" ${ARGN})
  if (TORCH_ENABLE_CUDA_BACKEND)
    set(CUDA_SRCS "${ARG_UNPARSED_ARGUMENTS}")
    list(FILTER CUDA_SRCS INCLUDE REGEX ".*cu$")
    if (CUDA_SRCS)
      cuda_add_library(${target_name}_cuda_tmp STATIC ${CUDA_SRCS})
      target_include_directories(${target_name}_cuda_tmp PRIVATE ${ARG_EXTRA_INCLUDE_DIRS})
      target_link_libraries(${target_name}_cuda_tmp ${ARG_EXTRA_LINK_LIBRARIES})
      target_compile_definitions(${target_name}_cuda_tmp PRIVATE
        TORCH_EXTENSION_NAME=${target_name}
        TORCH_MAJOR_VERSION=${TORCH_MAJOR_VERSION}
        TORCH_MINOR_VERSION=${TORCH_MINOR_VERSION}
        ENABLE_CUDA_BACKEND=${TORCH_ENABLE_CUDA_BACKEND}
        ${ARG_EXTRA_DEFINITIONS})
      set_target_properties(${target_name}_cuda_tmp PROPERTIES
        POSITION_INDEPENDENT_CODE ON
        CXX_VISIBILITY_PRESET "hidden"
        CUDA_VISIBILITY_PRESET "hidden"
        )
    endif()
  elseif (TORCH_ENABLE_HIP_BACKEND)
    set(HIP_SRCS "${ARG_UNPARSED_ARGUMENTS}")
    list(FILTER HIP_SRCS INCLUDE REGEX ".*cu$")
    if (HIP_SRCS)
      HIP_ADD_LIBRARY(${target_name}_hip_tmp STATIC ${HIP_SRCS})
      target_include_directories(${target_name}_hip_tmp PRIVATE ${ARG_EXTRA_INCLUDE_DIRS})
      target_link_libraries(${target_name}_hip_tmp ${ARG_EXTRA_LINK_LIBRARIES})
      target_compile_definitions(${target_name}_hip_tmp PRIVATE
        TORCH_EXTENSION_NAME=${target_name}
        TORCH_MAJOR_VERSION=${TORCH_MAJOR_VERSION}
        TORCH_MINOR_VERSION=${TORCH_MINOR_VERSION}
        ENABLE_HIP_BACKEND=${TORCH_ENABLE_HIP_BACKEND}
        ${ARG_EXTRA_DEFINITIONS})
      set_target_properties(${target_name}_hip_tmp PROPERTIES
        POSITION_INDEPENDENT_CODE ON
        CXX_VISIBILITY_PRESET "hidden"
        )
    endif()
  endif()
  list(FILTER ARG_UNPARSED_ARGUMENTS EXCLUDE REGEX ".*cu$")
  pybind11_add_module(${target_name} MODULE ${ARG_UNPARSED_ARGUMENTS})
  target_include_directories(${target_name} PRIVATE ${ARG_EXTRA_INCLUDE_DIRS})
  if (TORCH_ENABLE_CUDA_BACKEND AND CUDA_SRCS)
    target_link_libraries(${target_name} PRIVATE ${target_name}_cuda_tmp ${ARG_EXTRA_LINK_LIBRARIES} torch ${TORCH_PYTHON_LIBRARY})
  elseif (TORCH_ENABLE_HIP_BACKEND AND HIP_SRCS)
    target_link_libraries(${target_name} PRIVATE ${target_name}_hip_tmp ${ARG_EXTRA_LINK_LIBRARIES} torch ${TORCH_PYTHON_LIBRARY})
  else()
    target_link_libraries(${target_name} PRIVATE ${ARG_EXTRA_LINK_LIBRARIES} torch ${TORCH_PYTHON_LIBRARY})
  endif()
  target_compile_definitions(${target_name} PRIVATE
    TORCH_EXTENSION_NAME=${target_name}
    TORCH_VERSION_MAJOR=${TORCH_VERSION_MAJOR}
    TORCH_VERSION_MINOR=${TORCH_VERSION_MINOR}
    ENABLE_CUDA_BACKEND=${TORCH_ENABLE_CUDA_BACKEND}
    ENABLE_HIP_BACKEND=${TORCH_ENABLE_HIP_BACKEND}
    ${ARG_EXTRA_DEFINITIONS})
endfunction()
