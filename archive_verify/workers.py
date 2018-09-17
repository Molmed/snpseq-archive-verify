import logging
import rq
import subprocess
import os
import datetime

from archive_verify.pdc_client import PdcClient, MockPdcClient

log = logging.getLogger(__name__)


def compare_md5sum(archive_dir):
    """
    Calculates the MD5 sums of the specified archive and compares them to the previously generated checksums 
    that were uploaded together with the archive to PDC. 

    :param archive_dir: The path to the archive that we shall verify
    :returns True if no errors or warnings were encountered when calculating checksums, otherwise False 
    """
    parent_dir = os.path.abspath(os.path.join(archive_dir, os.pardir))
    md5_output = os.path.join(parent_dir, "compare_md5sum.out")
    cmd = "cd {} && md5sum -c ./{} > {}".format(archive_dir, "checksums_prior_to_pdc.md5", md5_output)
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    p.communicate()

    if p.returncode != 0: 
        return False
    else: 
        return True


def get_pdc_client_class(config):
    """
    Determines which PDC Client should be used.

    :param config: A dict containing the apps configuration
    :returns A PDC Client.
    """
    return MockPdcClient if config.get("pdc_client", "PdcClient") == "MockPdcClient" else PdcClient


def configure_log(dsmc_log_dir, archive_pdc_description):
    now_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
    log.setLevel(logging.DEBUG)
    fh = logging.FileHandler(os.path.join(dsmc_log_dir, "{}-{}.log".format(archive_pdc_description, now_str)))
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    log.addHandler(fh)


def verify_archive(archive_name, archive_pdc_path, archive_pdc_description, config):
    """
    Our main worker function. This will be put into the RQ/Redis queue when the /verify endpoint gets called. 
    Downloads the specified archive from PDC and then verifies the MD5 sums. 

    :param archive_name: The name of the archive we shall download
    :param archive_pdc_path: The path in PDC TSM to the archive that we want to download
    :param archive_pdc_description: The unique description that was used when uploading the archive to PDC
    :param config: A dict containing the apps configuration
    :returns A JSON with the result that will be kept in the Redis queue
    """
    dsmc_log_dir = config["dsmc_log_dir"]
    configure_log(dsmc_log_dir, archive_pdc_description)
    log.debug("verify_archive started for {}".format(archive_name))

    pdc_class = get_pdc_client_class(config)
    log.debug(f"Using PDC Client of type: {pdc_class.__name__}")

    job_id = rq.get_current_job().id
    pdc_client = pdc_class(archive_name, archive_pdc_path, archive_pdc_description, job_id, config)
    dest = pdc_client.dest()
    download_ok = pdc_client.download()

    if not download_ok:
        log.debug("Download of {} failed.".format(archive_name))
        return {"state": "error", "msg": "failed to properly download archive from pdc", "path": dest}
    else:
        log.debug("verifying {}".format(archive_name))
        archive = os.path.join(dest, archive_name)
        verified_ok = compare_md5sum(archive)
        output_file = "{}/compare_md5sum.out".format(dest)

        if verified_ok:
            log.debug("Verify of {} succeeded.".format(archive))
            return {"state": "done", "path": output_file, "msg": "sucessfully verified archive md5sums"}
        else:
            log.debug("Verify of {} failed.".format(archive))
            return {"state": "error", "path": output_file, "msg": "failed to verify archive md5sums"}
