CONTAINER=tart_tools

test:
	apptainer run ${CONTAINER}.sif tart2ms --help

build:
	mkdir -p ~/tmp
	APPTAINER_TMPDIR=~/tmp apptainer build --fakeroot ${CONTAINER}.sif Singularity.def

docker:
	docker build .
	docker exec
