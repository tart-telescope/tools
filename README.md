# TART telescope tools

Containerized tools for using the TART radio telescope. This repository creates a TART tools container. It is recommended that this container be used using apptainer (or singularity). The tools available are

* tart2ms: Create and manipulate measurement sets from TART data
* disko: Discrete Sky Operator imaging. Ideal for working with wide-field TART data.
* All of the tart_tools python package.

## Building

For the moment, you can build locally. The command

    make build

Will create an apptainer application tart_tools.sif that can run any of the commands.

## ToDo

* Put the container on docker hub.

## Changelog

* March 2025. Initial commit.
