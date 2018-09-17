import re
import logging
import os
import subprocess
import fnmatch

# Share pre-configured workers log
log = logging.getLogger('archive_verify.workers')


class PdcClient():
    """
    Base class representing a PDC client.
    Staging and production environments should instantiate PdcClient (default).
    Local and testing environments should instantiate MockPdcClient.
    """
    def __init__(self, archive_name, archive_pdc_path, archive_pdc_description, job_id, config):
        """
        :param archive_name: The name of the archive we shall download
        :param archive_pdc_path: The path in PDC TSM to the archive that we want to download
        :param archive_pdc_description: The unique description that was used when uploading the archive to PDC
        :param job_id: The current rq worker job id
        :param config: A dict containing the apps configuration
        """
        self.dest_root = config["verify_root_dir"]
        self.dsmc_log_dir = config["dsmc_log_dir"]
        self.whitelisted_warnings = config["whitelisted_warnings"]
        self.archive_name = archive_name
        self.archive_pdc_path = archive_pdc_path
        self.archive_pdc_description = archive_pdc_description
        self.job_id = job_id

    def dest(self):
        """
        :returns The unique path where the archive will be downloaded.
        """
        return "{}_{}".format(os.path.join(self.dest_root, self.archive_name), self.job_id)

    def download(self):
        """
        Downloads the specified archive from PDC to a unique location.
        :returns True if no errors or only whitelisted warnings were encountered, False otherwise
        """
        log.debug("download_from_pdc started for {}".format(self.archive_pdc_path))
        cmd = "export DSM_LOG={} && dsmc retr {}/ {}/ -subdir=yes -description='{}'".format(self.dsmc_log_dir,
                                                                                            self.archive_pdc_path,
                                                                                            self.dest(),
                                                                                            self.archive_pdc_description)
        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

        dsmc_output, _ = p.communicate()
        dsmc_exit_code = p.returncode

        if dsmc_exit_code != 0:
            return PdcClient._parse_dsmc_return_code(dsmc_exit_code, dsmc_output, self.whitelisted_warnings)

        log.debug("download_from_pdc completed successfully for {}".format(self.archive_pdc_path))
        return True

    def downloaded_archive_path(self):
        return os.path.join(self.dest(), self.archive_name)

    @staticmethod
    def _parse_dsmc_return_code(exit_code, output, whitelist):
        """
        Parses the dsmc output when we've encountered a non-zero exit code. For some certain exit codes,
        warnings and errors we still want to return successfully.

        :param exit_code: The exit code received from the failing dsmc process
        :param output: The text output from the dsmc process
        :param whitelist: A list of whitelisted warnings
        :returns True if only whitelisted warnings was encountered in the output, otherwise False
        """
        log.debug("DSMC process returned an error!")

        # DSMC sets return code to 8 when a warning was encountered.
        if exit_code == 8:
            log.debug("DSMC process actually returned a warning.")

            output = output.splitlines()

            # Search through the DSMC log and see if we only have
            # whitelisted warnings. If that is the case, change the
            # return code to 0 instead. Otherwise keep the error state.
            warnings = []

            for line in output:
                matches = re.findall(r'ANS[0-9]+W', line)

                for match in matches:
                    warnings.append(match)

            log.debug("Warnings found in DSMC output: {}".format(set(warnings)))

            for warning in warnings:
                if warning not in whitelist:
                    log.error("A non-whitelisted DSMC warning was encountered. Reporting it as an error! ('{}')".format(
                        warning))
                    return False

            log.debug("Only whitelisted DSMC warnings were encountered. Everything is OK.")
            return True
        else:
            log.error("An uncaught DSMC error code was encountered!")
            return False


class MockPdcClient(PdcClient):
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
        """
        Instead of downloading the specified archive from PDC, this method
        checks the dest dir for a pre-downloaded archive with the specified name.
        This can be used to test archive verification in environments where
        dsmc cannot be easily installed, e.g. local development environments.

        To use this method, copy an archive that has been pre-downloaded from PDC
        into the verify_root_dir. Delete or edit some files from the archive if
        you wish to trigger a validation error.
        """

        if not self.predownloaded_archive_path:
            log.error(f"No archive containing the name {self.archive_name} found in {self.dest_root}")
            return False
        else:
            log.debug(f"Found pre-downloaded archive at {self.predownloaded_archive_path}")
            return True

