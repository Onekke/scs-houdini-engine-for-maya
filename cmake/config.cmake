set(ENV{MAYA_ROOT} "C:/Program Files/Autodesk/Maya2022/")
set(ENV{HOUDINI_ROOT} "C:/Program Files/Side Effects Software/Houdini 20.0.688/")


set(CMAKE_CONFIGURATION_TYPES "Debug;Release")
set(CMAKE_INSTALL_PREFIX "C:/Program Files/Maya")

set(MAYA_VERSION "2022")
set(Maya_INCLUDE_DIRS "$ENV{M_ROOT}include")
set(Maya_Foundation "$ENV{M_ROOT}lib/Foundation.lib")
set(Maya_OpenMaya "$ENV{M_ROOT}lib/OpenMaya.lib")
set(Maya_OpenMayaAnim "$ENV{M_ROOT}lib/OpenMayaAnim.lib")
set(Maya_OpenMayaFX "$ENV{M_ROOT}lib/OpenMayaFX.lib")
set(Maya_ROOT "$ENV{M_ROOT}")

set(HoudiniEngine_ROOT "$ENV{H_ROOT}")
set(HoudiniEngine_BINARY_DIR "$ENV{H_ROOT}bin")
set(HoudiniEngine_HAPIL "$ENV{H_ROOT}custom/houdini/dsolib/libHAPIL.lib")
set(HoudiniEngine_INCLUDE_DIRS  "$ENV{H_ROOT}toolkit/include")