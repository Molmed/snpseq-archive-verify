import logging
import os

from aiohttp import web
from rq import Queue

import archive_verify
from archive_verify.workers import verify_archive
import archive_verify.redis_client as redis_client

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
    endpoint = request.match_info["endpoint"]
    keep_download = (endpoint == "download")
    host = body["host"]
    archive = body["archive"]
    description = body["description"]
    path = body.get("path")

    src_root = request.app["config"]["pdc_root_dir"].format(host)
    # use a supplied path if available, otherwise construct it from the src_root and archive
    archive_path = path or os.path.join(src_root, archive)

    q = request.app['redis_q']

    # Enqueue the verify_archive function with the user supplied input parameters.
    # Note that the TTL and timeout parameters are important for e.g. how long
    # the jobs and their results will be kept in the Redis queue. By default our
    # config e.g. setups the queue to keep the job results indefinately,
    # therefore they we will have to remove them ourselves afterwards.
    job = q.enqueue_call(verify_archive,
                         args=(
                            archive,
                            archive_path,
                            description,
                            keep_download,
                            request.app["config"]),
                         timeout=request.app["config"]["job_timeout"],
                         result_ttl=request.app["config"]["job_result_ttl"],
                         ttl=request.app["config"]["job_ttl"])

    url = request.url
    url_base = request.app["config"]["base_url"]

    status_end_point = "{0}://{1}:{2}{3}/status/{4}".format(
        url.scheme,
        url.host,
        url.port,
        url_base,
        job.id)
    response = {
        "status": archive_verify.REDIS_STATES.get(
            job.get_status(),
            archive_verify.State.NONE),
        "job_id": job.id,
        "link": status_end_point,
        "path": archive_path,
        "action": endpoint}

    return web.json_response(response)


async def status(request):
    """
    Handler accepts a GET call with an URL parameter which corresponds to a previously 
    enqueued job. The endpoint will return with the current status of the requested job. 

    :param job_id: The UUID4 of a previsouly enqueued verify job
    :return A JSON containing the current status of a verify job. 
    """
    job_id = str(request.match_info['job_id'])

    q = request.app['redis_q']
    job = q.fetch_job(job_id)

    if job is None:
        return web.json_response(
            {
                "state": archive_verify.State.ERROR,
                "msg": f"No such job {job_id} found!"
            },
            status=400
        )

    job_state = archive_verify.REDIS_STATES.get(
        job.get_status(),
        archive_verify.State.NONE)
    payload = {
        "state": job_state
    }
    code = 200

    if job_state in [
        archive_verify.State.DONE,
        archive_verify.State.ERROR
    ]:
        # this is the dict returned by the worker function
        job_result = job.result
        job_result_state = job_result["state"]
        payload["state"] = job_result_state
        payload["msg"] = f"Job {job_id} has returned with result: {job_result['msg']}"

        if job_result_state == archive_verify.State.ERROR:
            payload["debug"] = job.exc_info if job.exc_info else job_result
            code = 500

        job.delete()
    elif job_state == archive_verify.State.STARTED:
        payload["msg"] = f"Job {job_id} is currently running."
    else:
        payload["msg"] = f"Job {job_id} is {job_state}"

    return web.json_response(
        payload,
        status=code
    )


async def redis_context(app):
    app["redis_q"] = Queue(
        connection=redis_client.get_redis_instance(),
        is_async=app["config"].get("async_redis", True))
    yield
