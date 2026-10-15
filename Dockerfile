# 构建环境（工具链）——"拿来即用"
#   docker build -t staticpy .
#   docker run --rm -v $PWD:/w -w /w staticpy bash selfcheck.sh
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential pkg-config git ca-certificates \
      python3 python3-pip \
      libgif-dev libwebp-dev libtiff-dev libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

# Chez Scheme（AOT 后端）——构建树保留在 /opt/ChezScheme/ta6le（脚本默认布局）
RUN git clone --depth 1 https://github.com/cisco/ChezScheme /src/ChezScheme \
 && cd /src/ChezScheme && ./configure --threads && make -j"$(nproc)" \
 && mkdir -p /opt/ChezScheme && cp -r /src/ChezScheme/ta6le /opt/ChezScheme/

# "测量"侧（差分测试对照用；不进产物）
RUN pip3 install --break-system-packages --no-cache-dir pillow numpy

ENV CHEZ_SCHEME_DIR=/opt/ChezScheme/ta6le \
    CHEZ_BOOT_DIR=/opt/ChezScheme/boot/ta6le
WORKDIR /w
CMD ["bash", "selfcheck.sh"]
