FROM python:3.9-slim

COPY . /archive-verify
WORKDIR /archive-verify

# install services
RUN \
  apt-get update && \
  apt-get install -y git redis gcc nginx nano && \
  cp docker/nginx.conf /etc/nginx/nginx.conf && \
  rm -rf .venv && \
  python3 -m venv --upgrade-deps .venv && \
  .venv/bin/pip install -e .[test]

RUN \
  .venv/bin/nosetests tests/
  
# setup test data
RUN \
  mkdir -p data/test_host/runfolders && \
  mkdir -p logs && \
  mkdir -p data/verify/test_1_archive/test_1_archive && \
  mkdir -p data/verify/test_2_archive/test_2_archive && \
  cd data/verify/test_1_archive/test_1_archive && \
  dd if=/dev/urandom of=test_1_data count=4000 bs=1024 && \
  md5sum test_1_data > checksums_prior_to_pdc.md5 && \
  cd ../../test_2_archive/test_2_archive && \
  dd if=/dev/urandom of=test_2_data count=4000 bs=1024 && \
  md5sum test_2_data > checksums_prior_to_pdc.md5 && \
  cd ../../../..

EXPOSE 9898 9899

CMD [ "docker/start.sh" ]
