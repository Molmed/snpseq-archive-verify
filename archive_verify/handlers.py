import json
import logging
import os

from aiohttp import web
from redis import Redis
from rq import Queue

from archive_verify.workers import verify_archive

log = logging.getLogger(__name__)

async def verify(request):
    """
    Handler accepts a POST call with JSON parameters in the body. Upon a request it will 
    enqueue a job that will verify the uploaded archive's MD5 sums. The enqueued job 
    function later gets picked up by the separte RQ worker process. 

    :param archive: Name of the archive we want to download and verify MD5 sums for
    :param description: The unique description used when uploading the archive to PDC
    :param host: From which host we uploaded the archive
    :return JSON containing job id and link which we can poll for current job status
    """
    body = await request.json()
    host = body["host"]
    archive = body["archive"]
    description = body["description"]
    
    src_root = request.app["config"]["pdc_root_dir"].format(host)
    archive_path = os.path.join(src_root, archive) 

    redis_conn = Redis()
    q = Queue(connection=redis_conn)

    # Enqueue the verify_archive function with the user supplied input parameters.
    # Note that the TTL and timeout parameters are important for e.g. how long 
    # the jobs and their results will be kept in the Redis queue. By default our 
    # config e.g. setups the queue to keep the job results indefinately, 
    # therefore they we will have to remove them ourselves afterwards. 
    job = q.enqueue_call(verify_archive, 
                        args=(archive, host, description, request.app["config"]),
                        timeout=request.app["config"]["job_timeout"],
                        result_ttl=request.app["config"]["job_result_ttl"],
                        ttl=request.app["config"]["job_ttl"])

    url = request.url
    url_base = request.app["config"]["base_url"]

    status_end_point = "{0}://{1}:{2}{3}/status/{4}".format(url.scheme, url.host, url.port, url_base, job.id)
    response = { "status": "pending", "job_id": job.id, "link": status_end_point, "path": archive_path }
    
    return web.json_response(response)

async def status(request):
    """
    Handler accepts a GET call with an URL parameter which corresponds to a previously 
    enqueued job. The endpoint will return with the current status of the requested job. 

    :param job_id: The UUID4 of a previsouly enqueued verify job
    :return A JSON containing the current status of a verify job. 
    """
    job_id = str(request.match_info['job_id'])

    redis_conn = Redis()
    q = Queue(connection=redis_conn)
    job = q.fetch_job(job_id)

    if job:
        if job.is_started:
            payload = {"state": "started", "msg": "Job {} is currently running.".format(job_id)}
            code = 200
        elif job.is_finished:
            result = job.result

            if result and result["state"] == "done": 
                payload =  {"state": "done", "msg": "Job {} has returned with result: {}".format(job_id, job.result)}
                code = 200
            else: 
                payload =  {"state": "error", "msg": "Job {} has returned with result: {}".format(job_id, job.result), "debug": job.exc_info}
                code = 500

            job.delete()
        elif job.is_failed:
            payload = {"state": "error", "msg": "Job {} failed with error: {}".format(job_id, job.exc_info)}
            job.delete()
            code = 500
        else:
            payload = {"state": "pending", "msg": "Job {} has not started yet.".format(job_id)}
            code = 200
    else:
        payload = {"state": "error", "msg": "No such job {} found!".format(job_id)}
        code = 400

    return web.json_response(payload, status=code)
