.PHONY: build cmake hipify unittest run.%

cmake:
	cd build && cmake .. -DCMAKE_INSTALL_PREFIX=../install -DBOOST_ROOT=/datamy/test/projects/dreamplace.workspace/boost_1_86_0 -DPython_EXECUTABLE=/datamy/test/anaconda3/envs/dreamplace/bin/python

build:
	cd build && make -j32 && make install

hipify:
	find ./dreamplace -name "*.cu" -o -name "*.cuh" | xargs -P 8 -I {} sh -c 'echo "Processing {}"; hipify {} -inplace'

debug_run.%:
	cd build && make install && cd ../install && HIP_LAUNCH_BLOCKING=1 AMD_LOG_LEVEL=2 python dreamplace/Placer.py test/ispd2005/$*.json 2>&1 | tee $*.log

unittest:
	cd build && make install && cd ../install && HIP_LAUNCH_BLOCKING=1 AMD_LOG_LEVEL=2 python unittest/ops/hpwl_unittest.py