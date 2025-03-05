CONTAINER=tart_tools
PWD=`pwd`
test:
	apptainer run ${CONTAINER}.sif tart2ms --help

alias:
	echo "alias tart_tools='apptainer run ${PWD}/${CONTAINER}.sif'"
build:
	mkdir -p ~/tmp
	APPTAINER_TMPDIR=~/tmp apptainer build --fakeroot ${CONTAINER}.sif Singularity.def

docker:
	docker build -t tart_tools .
	docker run -i -t tart_tools tart2ms --help
