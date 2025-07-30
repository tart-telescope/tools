FROM debian:bookworm
LABEL Maintainer="Tim Molteno tim@elec.ac.nz"
LABEL org.opencontainers.image.description="TART radio telescope tools"
ARG DEBIAN_FRONTEND=noninteractive

# debian setup
RUN apt-get update -y && apt-get install -y \
    curl \
    pkg-config \
    python3-venv python3-setuptools \
    python3-dev python3-wheel python3-pkgconfig \
    python3-cffi libffi-dev libhdf5-dev \
    python3-numpy python3-scipy \
    python3-matplotlib \
    python3-h5py python3-astropy \
    python3-pandas python3-gmsh \
    python3-dask python3-healpy
# RUN apt-get install -y cython3
#
# RUN rm -rf /var/lib/apt/lists/*
#
ENV PYTHONDONTWRITEBYTECODE=1
# ENV OPENBLAS_NUM_THREADS=1
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV

RUN . /opt/venv/bin/activate && pip3 install --upgrade pip
# RUN . /opt/venv/bin/activate && pip3 install --no-cache-dir --no-compile --no-deps tart  # --no-deps to avoid depending on h5py
# RUN . /opt/venv/bin/activate && pip3 install --no-cache-dir --no-compile "minio<=7.1"
# RUN . /opt/venv/bin/activate && pip3 install --no-cache-dir --no-compile --no-deps tart_tools
RUN . /opt/venv/bin/activate && pip3 install --no-cache-dir --no-compile git+https://github.com/tart-telescope/tart2ms.git
RUN . /opt/venv/bin/activate && pip3 install --no-cache-dir --no-compile git+https://github.com/tmolteno/disko.git
RUN . /opt/venv/bin/activate && pip3 install --no-cache-dir --no-compile git+https://github.com/tmolteno/spotless.git
RUN . /opt/venv/bin/activate && pip3 install --no-cache-dir --no-compile --upgrade astropy-iers-data
ENV PATH="/opt/venv/bin:${PATH}"
