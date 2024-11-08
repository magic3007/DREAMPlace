.PHONY: build cmake hipify

hipify:
	find ./dreamplace -name "*.cu" -o -name "*.cuh" | xargs -P 8 -I {} sh -c 'echo "Processing {}"; hipify {} -inplace'

cmake:
	cd build && cmake .. -DCMAKE_INSTALL_PREFIX=../install -DBOOST_ROOT=/datamy/test/projects/dreamplace.workspace/boost_1_86_0 -DPython_EXECUTABLE=/datamy/test/anaconda3/envs/dreamplace/bin/python

build:
	cd build && make && make install

run.%:
	cd build && make install && cd ../install && python dreamplace/Placer.py test/ispd2005/$*.json 2>&1 | tee $*.log