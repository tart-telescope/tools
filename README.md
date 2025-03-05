# TART telescope tools

Containerized tools for using the TART radio telescope. This repository creates a TART tools container. It is recommended that this container be used using apptainer (or singularity). The tools available are

* tart2ms: Create and manipulate measurement sets from TART data
* disko: Discrete Sky Operator imaging. Ideal for working with wide-field TART data.
* disko_draw: Draw and visualize discrete fields of view
* All of the tart_tools python package.
** tart_download_data

## Create an alias called tart_tools

    make build
    alias tart_tools='apptainer run /home/tim/tart-telescope/tools/tart_tools.sif'

## Using

    tart_tools tart_download_data --vis --api https://api.elec.ac.nz/tart/mu-udm --n 1

    tart_tools tart2ms --hdf vis_2025-03-05_13_04_41.765325.hdf --single-field --rephase obs-midpoint --ms udm.ms
    
    tart_tools disko --ms udm.ms --nvis 10000 --healpix --fov 170deg --res 30arcmin  --lasso --alpha 0.005 --HDF tart_udm_image.h5

### Draw sources on the image

    tart_tools disko_draw --show-sources --SVG tart_udm_image.svg tart_udm_image.h5
    convert -resize 25% tart_udm_image.svg img/tart_udm_image.jpg
    
![TART radio image](img/tart_udm_image.jpg)

## Building

For the moment, you can build locally. The command

    make build

Will create an apptainer application tart_tools.sif that can run any of the commands.

## ToDo

* Put the container on docker hub.

## Changelog

* March 2025. Initial commit.
