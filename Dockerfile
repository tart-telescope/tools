FROM debian:bookworm AS builder
LABEL Maintainer="Tim Molteno tim@elec.ac.nz"
LABEL org.opencontainers.image.description="TART radio telescope tools"
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update -y && apt-get install -y curl build-essential

WORKDIR /build
RUN curl -o rustup.sh --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs
RUN sh rustup.sh -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN cargo install tart-gnss-acquire --root /usr/local

FROM debian:bookworm AS runner
LABEL Maintainer="Tim Molteno tim@elec.ac.nz"
LABEL org.opencontainers.image.description="TART radio telescope tools"
ARG DEBIAN_FRONTEND=noninteractive

# debian setup
RUN apt-get update -y && apt-get install -y \
    curl \
    casacore-dev \
    gcc g++ \
    libblas-dev liblapack-dev \
    wcslib-dev libcfitsio-dev \
    libboost-python-dev \
    cmake ninja-build \
    pkg-config \
    python3-venv python3-setuptools \
    python3-dev python3-wheel python3-pkgconfig \
    python3-cffi libffi-dev libhdf5-dev \
    python3-numpy python3-scipy \
    python3-matplotlib \
    python3-h5py python3-astropy \
    python3-pandas python3-gmsh \
    python3-dask
#
COPY --from=builder /usr/local/bin/tart-gnss-acquire /usr/bin/tart-gnss-acquire

RUN rm -rf /var/lib/apt/lists/*
#
ENV PYTHONDONTWRITEBYTECODE=1
# ENV OPENBLAS_NUM_THREADS=1
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

ENV CMAKE_ARGS="-DCMAKE_CXX_STANDARD=17"
ENV REDO=1
RUN pip install --upgrade pip

RUN pip install --no-cache-dir --no-compile "python-casacore>=3.5.0" "tart2ms>=0.9.0" disko spotless
RUN pip install --no-cache-dir --no-compile --upgrade astropy-iers-data
