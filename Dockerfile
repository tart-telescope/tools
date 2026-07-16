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

FROM python:3.13-slim AS runner
LABEL Maintainer="Tim Molteno tim@elec.ac.nz"
LABEL org.opencontainers.image.description="TART radio telescope tools"
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    casacore-dev \
    gcc g++ \
    libblas-dev liblapack-dev \
    wcslib-dev libcfitsio-dev \
    libboost-python-dev \
    cmake ninja-build \
    casacore-data \
    && rm -rf /var/lib/apt/lists/*
#
COPY --from=builder /usr/local/bin/tart-gnss-acquire /usr/bin/tart-gnss-acquire
#
ENV CMAKE_ARGS="-DCMAKE_CXX_STANDARD=17"

RUN pip install --no-cache-dir python-casacore \
            "tart2ms>=0.9.2" \
            "disko>=1.4.4" \
            "spotless>=0.7.5" \
            "tart_tools >= 1.4.5"
RUN pip install --no-cache-dir --upgrade \
            astropy-iers-data
