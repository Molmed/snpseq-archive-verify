SNPSEQ Archive Verify
==================

A self contained (aiohttp) REST service that helps verify uploaded SNP&SEQ archives by first downloading the archive from PDC, and then compare the MD5 sums for all associated files. 

The web service enqueues certain job functions in the RQ/Redis queue, where they get picked up by the separate RQ worker process. 

Trying it out
-------------

    python3 -m pip install pipenv
    pipenv install --deploy
    apt-get install redis-server

Try running it:

     pipenv run ./archive-verify-ws -c=config/
     pipenv run rq worker

Running tests
-------------

    pipenv install --dev
    pipenv run nosetests tests/

REST endpoints
--------------

Enqueue a verification job of a specific archive: 
    
    curl -i -X "POST" -d '{"host": "my-host", "description": "my-descr", "archive": "my_001XBC_archive"}' http://localhost:8989/api/1.0/verify

Check the current status of an enqueued job: 

    curl -i -X "GET" http://localhost:8989/api/1.0/status/<job-uuid-returned-from-verify-endpoint>


