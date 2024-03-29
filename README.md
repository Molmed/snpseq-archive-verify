SNPSEQ Archive Verify
==================

A self contained (aiohttp) REST service that helps verify uploaded SNP&SEQ archives by first downloading the archive 
from PDC, and then compare the MD5 sums for all associated files. The downloaded files are deleted on successful 
verification, and retained if any error occurs.

The service is composed of 3 components which must all be running and the system must be set up to allow the services 
to communicate over the configured protocols and ports (refer to the redis documentation for details):

- archive-verify-ws REST service
- Redis queue server
- RQ worker

The web service enqueues certain job functions in the RQ/Redis queue, where they get picked up by the separate RQ 
worker process.  

Pre-requisites
--------------
You will need python >=3.9 and redis.

[Download and install redis](https://redis.io/docs/getting-started/installation/install-redis-on-linux/)


Install
-------
It is recommended to set up the service in a virtual environment. [venv](https://docs.python.org/3/library/venv.html) 
is used below with bash on a Linux system. 

    python3 -m venv --upgrade-deps .venv
    source .venv/bin/activate
    pip install .

Running the service
-------------------

Start the Redis server and RQ worker:

    redis-server
    rq worker

Start the REST service

    archive-verify-ws -c=config/


Mock Downloading
----------------

If you are running this service locally and don't have IBM's dsmc client installed, you can skip the downloading step 
and verify an archive that is already on your machine.

To use this method:
- copy an archive that has been pre-downloaded from PDC into the verify_root_dir set in app.yaml
- Delete or edit some files from the archive if you wish to trigger a validation error.
- in app.yml, set:

    pdc_client: "MockPdcClient"
    
*Note that the archive will be deleted from verify_root_dir on successful verification*

#### Naming Conventions for Mock Download ####
Note that when an archive is downloaded from PDC using snpseq-archive-verify, the downloaded directory is formatted 
with the name of the archive plus the RQ job id, like so:

    {verify_root_dir}/{archive_name}_{rq_job_id}

When mocking downloading, we search verify_root_dir for archive_name and use the first directory found, ignoring the 
rq_job_id.


Running tests
-------------

    source .venv/bin/activate
    pip install -e .[test]
    nosetests tests/

REST endpoints
--------------

Enqueue a verification job of a specific archive: 
    
    curl -i -X "POST" -d '{"host": "my-host", "description": "my-descr", "archive": "my_001XBC_archive"}' http://localhost:8989/api/1.0/verify

Enqueue a download job of a specific archive:

    curl -i -X "POST" -d '{"host": "my-host", "description": "my-descr", "archive": "my_001XBC_archive"}' http://localhost:8989/api/1.0/download

Check the current status of an enqueued job: 

    curl -i -X "GET" http://localhost:8989/api/1.0/status/<job-uuid-returned-from-verify-endpoint>

Docker container
----------------

For testing purposes, you can also build a Docker container using the resources in the docker/ folder:

    # build and start Docker container
    docker/up

This will build and start a Docker container that runs a nginx proxy server which will listen to connections on ports 
9898 and 9899 and forward traffic to the archive-verify service running internally. API calls to port 9898 are done as
described above, e.g.:

    # interact with archive-verify service on port 9898
    curl 127.0.0.1:9898/api/1.0/status/1

API calls to port 9899 emulate how calls to the service running on Uppmax is done (i.e., going through a gateway). The
first path element for these calls should be verify/, e.g.:

    # interact with archive-verify service on port 9899
    curl 127.0.0.1:9899/verify/api/1.0/status/1

The container log output can be followed:

    # follow the container log output (Ctrl+C to stop)
    docker/log

In addition, the archive-verify service in the container is running with the MockPdcClient enabled. In the container,
there are two folders that can be used for testing with the mock client, `test_1_archive` and `test_2_archive`, e.g.:

    # enque a download job of the test archive available in the container
    curl \
      -X "POST" \
      -d '{"host": "test_host", "description": "my-descr", "archive": "test_1_archive"}' \
      http://localhost:9898/api/1.0/download

      # {
      #   "status": "pending",
      #   "job_id": "d7a26f2e-d410-4a9b-a308-973821d0a021",
      #   "link": "http://localhost:9898/api/1.0/status/d7a26f2e-d410-4a9b-a308-973821d0a021",
      #   "path": "data/test_host/runfolders/test_1_archive",
      #   "action": "download"
      # }

    # check the status of the download job
    curl \
      http://localhost:9898/api/1.0/status/d7a26f2e-d410-4a9b-a308-973821d0a021

      # {
      #   "state": "done",
      #   "msg": "Job d7a26f2e-d410-4a9b-a308-973821d0a021 has returned with result: Successfully verified archive md5sums."
      # }

    # enque a verify job of the test archive available in the container, emulating a call to the service on Uppmax
    curl \
      -X "POST" \
      -d '{"host": "test_host", "description": "my-descr", "archive": "test_2_archive"}' \
      http://localhost:9899/verify/api/1.0/verify

      # {
      #   "status": "pending",
      #   "job_id": "0124bdcb-7f31-4402-9251-ae766306ad49",
      #   "link": "http://localhost:9899/api/1.0/status/0124bdcb-7f31-4402-9251-ae766306ad49",
      #   "path": "data/test_host/runfolders/test_2_archive",
      #   "action": "verify"
      # }

    # check the status of the download job
    curl \
      http://localhost:9899/verify/api/1.0/status/0124bdcb-7f31-4402-9251-ae766306ad49

      # {
      #   "state": "done",
      #   "msg": "Job 0124bdcb-7f31-4402-9251-ae766306ad49 has returned with result: Successfully verified archive md5sums."
      # }

The docker container can be stopped and removed:

    # stop and remove the running docker container
    docker/down
