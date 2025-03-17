CONTAINER=tart_tools
PWD=`pwd`

TEST_CMD=tart2ms --hdf /test/vis_2025-03-09_06_26_46.859046.hdf --ms test/test.ms --clobber
testap:
	apptainer run ${CONTAINER}.sif ${TEST_CMD}

alias:
	echo "alias tart_tools='apptainer run ${PWD}/${CONTAINER}.sif'"
build:
	mkdir -p ~/tmp
	APPTAINER_TMPDIR=~/tmp apptainer build --fakeroot ${CONTAINER}.sif tart_tools.def

docker:
	docker build -t tart_tools .

testd:
	docker run --mount type=bind,source=./test,target=/test -i -t tart_tools tart2ms \
		--hdf /test/vis_2025-03-09_06_26_46.859046.hdf \
		--add-model \
		--ms /test/test.ms --clobber
