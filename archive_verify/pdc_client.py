import fnmatch
import logging
import os
import re
import shutil
import subprocess

# Share pre-configured workers log
log = logging.getLogger('archive_verify.workers')


class PdcClient:
    """
    Base class representing a PDC client.
    Staging and production environments should instantiate PdcClient (default).
    Local and testing environments should instantiate MockPdcClient.
    """
    def __init__(self, archive_name, archive_pdc_path, archive_pdc_description, job_id, config):
        """
        :param archive_name: The name of the archive we shall download
        :param archive_pdc_path: The path in PDC TSM to the archive that we want to download
        :param archive_pdc_description: The unique description that was used when uploading the
        archive to PDC
        :param job_id: The current rq worker job id
        :param config: A dict containing the apps configuration
        """
        self.dest_root = config["verify_root_dir"]
        self.dsmc_log_dir = config["dsmc_log_dir"]
        self.whitelisted_warnings = config["whitelisted_warnings"]
        self.dsmc_extra_args = config.get("dsmc_extra_args", {})
        self.archive_name = archive_name
        self.archive_pdc_path = archive_pdc_path
        self.archive_pdc_description = archive_pdc_description
        self.job_id = job_id

    def dest(self):
        """
        :returns The unique path where the archive will be downloaded.
        """
        return f"{os.path.join(self.dest_root, self.archive_name)}_{self.job_id}"

    def dsmc_args(self):
        """
        Fetch a list of arguments that will be passed to the dsmc command line. If there are
        extra arguments specified in the config, with "dsmc_extra_args", these are included as well.
        If arguments specified in dsmc_extra_args has the same key as the default arguments, the
        defaults will be overridden.

        :return: a string with arguments that should be appended to the dsmc command line
        """
        key_values = {
            "subdir": "yes",
            "description": self.archive_pdc_description
        }
        key_values.update(self.dsmc_extra_args)
        args = [f"-{k}='{v}'" for k, v in key_values.items() if v is not None]
        args.extend([f"-{k}" for k, v in key_values.items() if v is None])
        return " ".join(args)

    def download(self):
        """
        Downloads the specified archive from PDC to a unique location.
        :returns True if no errors or only whitelisted warnings were encountered, False otherwise
        """
        log.info(f"Download_from_pdc started for {self.archive_pdc_path}")
        cmd = f"export DSM_LOG={self.dsmc_log_dir} && " \
              f"dsmc retr {self.archive_pdc_path}/ {self.dest()}/ {self.dsmc_args()}"

        p = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True)

        dsmc_output, _ = p.communicate()
        dsmc_exit_code = p.returncode

        if dsmc_exit_code != 0:
            return PdcClient._parse_dsmc_return_code(
                dsmc_exit_code, dsmc_output, self.whitelisted_warnings)

        log.info(f"Download_from_pdc completed successfully for {self.archive_pdc_path}")
        return True

    def downloaded_archive_path(self):
        return os.path.join(self.dest(), self.archive_name)

    def cleanup(self):
        shutil.rmtree(self.dest())

    @staticmethod
    def _parse_dsmc_return_code(exit_code, output, whitelist):
        """
        Parses the dsmc output when we've encountered a non-zero exit code. For some certain exit
        codes, warnings and errors we still want to return successfully.

        :param exit_code: The exit code received from the failing dsmc process
        :param output: The text output from the dsmc process
        :param whitelist: A list of whitelisted warnings
        :returns True if only whitelisted warnings was encountered in the output, otherwise False
        """

        # DSMC sets return code to 8 when a warning was encountered.
        log_fn = log.warning if exit_code == 8 else log.error
        log_fn(f"DSMC process returned a{' warning' if exit_code == 8 else 'n error'}!")

        # parse the DSMC output and extract error/warning codes and messages
        codes = []
        for line in output.splitlines():
            if line.startswith("ANS"):
                log_fn(line)

            matches = re.findall(r'ANS[0-9]+[EW]', line)
            for match in matches:
                codes.append(match)

        unique_codes = set(sorted(codes))
        if unique_codes:
            log_fn(f"ANS codes found in DSMC output: {', '.join(unique_codes)}")

            # if we only have whitelisted warnings, change the return code to 0 instead
            if unique_codes.issubset(set(whitelist)):
                log.info("Only whitelisted DSMC ANS code(s) were encountered. Everything is OK.")
                return True

        log.error(
            f"Non-whitelisted DSMC ANS code(s) encountered: "
            f"{', '.join(unique_codes.difference(set(whitelist)))}")
        return False


class MockPdcClient(PdcClient):
    """
    Instead of downloading the specified archive from PDC, the download method
    checks verify_root_dir for a pre-downloaded archive with the specified name.
    This can be used to test archive verification in environments where
    dsmc cannot be easily installed, e.g. local development environments.

    To use this method, copy an archive that has been pre-downloaded from PDC
    into the verify_root_dir. Delete or edit some files from the archive if
    you wish to trigger a validation error.
    """
    def __init__(self, archive_name, archive_pdc_path, archive_pdc_description, job_id, config):
        super().__init__(archive_name, archive_pdc_path, archive_pdc_description, job_id, config)

        self.predownloaded_archive_path = ''

        # Find a pre-downloaded archive with a matching name
        for file in os.listdir(os.path.join(self.dest_root)):
            if fnmatch.fnmatch(file, f'{self.archive_name}*'):
                self.predownloaded_archive_path = file

    def dest(self):
        """
        :returns The path of the predownloaded archive.
        """
        return os.path.join(self.dest_root, self.predownloaded_archive_path)

    def download(self):
        if not self.predownloaded_archive_path:
            log.error(
                f"No archive containing the name {self.archive_name} found in {self.dest_root}")
            return False
        else:
            log.info(
                f"Found pre-downloaded archive at {self.predownloaded_archive_path}")
            return True
