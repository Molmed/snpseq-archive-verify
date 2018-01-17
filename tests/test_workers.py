import mock
import unittest
import yaml

from archive_verify.workers import _parse_dsmc_return_code, download_from_pdc, compare_md5sum, verify_archive

class TestWorkers(unittest.TestCase):

    def setUp(self):
        with open("tests/test_config.yaml") as config:
            self.config = yaml.load(config)

    # Test with whitelisted warnings
    def test_dsmc_whitelist_ok(self):
        exit_code = 8
        whitelist = ["ANS2250W", "ANS5000W"]
        output = "TEST\nOUTPUT\nWARNING****************\nSEE ANS2250W FOR MORE INFO\nANS2250E\n"
        ret = _parse_dsmc_return_code(exit_code, output, whitelist)
        self.assertEqual(ret, True)

    # Test with non-whitelisted warnings
    def test_dsmc_whitelist_not_ok(self):
        exit_code = 8
        whitelist = ["ANS2250W", "ANS5000W"]
        output = "FOOBAR TEST OKEJ\nWARNING ERROR ANS221E TEST\n*** ANS5050W\n"
        ret = _parse_dsmc_return_code(exit_code, output, whitelist)
        self.assertEqual(ret, False)

    # Test with non-warning exit code
    def test_dsmc_unknown_exit_code(self): 
        exit_code=10
        whitelist = ["FOO", "BAR"]
        output = "FOO\nBAR\OK\n"
        ret = _parse_dsmc_return_code(exit_code, output, whitelist)
        self.assertEqual(ret, False)

    # Check when dsmc returns 0 
    @mock.patch('subprocess.Popen')
    def test_download_from_pdc_ok(self, mock_popen):
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.communicate.return_value = ("foobar", '')
        ret = download_from_pdc("archive", "descr", "dest", "log-dir", "whitelist")
        self.assertEqual(ret, True)
    
    # Check when dsmc returns != 0
    def test_download_from_pdc_with_ok_warning(self):
        exp_ret = "33232"

        with mock.patch('subprocess.Popen') as mock_popen, mock.patch('archive_verify.workers._parse_dsmc_return_code') as mock_parse_dsmc:  
            mock_popen.return_value.returncode = 42 
            mock_popen.return_value.communicate.return_value = ("foobar", '')
            mock_parse_dsmc.return_value = exp_ret
            ret = download_from_pdc("archive", "descr", "dest", "logdir", "whitelist")
            self.assertEqual(ret, exp_ret)

    # Check with passing checksums
    @mock.patch('subprocess.Popen')
    def test_compare_md5sum_ok(self, mock_popen): 
        mock_popen.return_value.returncode = 0 
        ret = compare_md5sum("archive-dir")
        self.assertEqual(ret, True)

    # Check with failing checksums
    @mock.patch('subprocess.Popen')
    def test_compare_md5sum_not_ok(self, mock_popen): 
        mock_popen.return_value.returncode = 42
        ret = compare_md5sum("archive-dir")
        self.assertEqual(ret, False)

    def test_verify_archive_download_not_ok(self): 
        with mock.patch('archive_verify.workers.download_from_pdc') as mock_download, mock.patch('rq.get_current_job') as mock_job: 
            job_id = "42-42-42-24-24-24"
            mock_download.return_value = False
            mock_job.return_value.id = job_id
            ret = verify_archive("my-archive", "my-host", "my-descr", self.config)
            self.assertEqual(ret["state"], "error")
            self.assertEqual(job_id in ret["path"], True)

    def test_verify_archive_verify_not_ok(self): 
        with mock.patch('archive_verify.workers.download_from_pdc') as mock_download, mock.patch('rq.get_current_job') as mock_job, mock.patch('archive_verify.workers.compare_md5sum') as mock_md5sum: 
            job_id = "24-24-24-24"
            archive = "my-archive-101"
            mock_download.return_value = True
            mock_job.return_value.id = job_id
            mock_md5sum.return_value = False
            ret = verify_archive(archive, "my-host", "my-descr", self.config)
            self.assertEqual(ret["state"], "error")
            self.assertEqual(archive in ret["path"], True)
		
    def test_verify_archive_verify_ok(self): 
        with mock.patch('archive_verify.workers.download_from_pdc') as mock_download, mock.patch('rq.get_current_job') as mock_job, mock.patch('archive_verify.workers.compare_md5sum') as mock_md5sum: 
            job_id = "24-24-24-24"
            archive = "my-archive-101" 
            mock_download.return_value = True
            mock_job.return_value.id = job_id
            mock_md5sum.return_value = True
            ret = verify_archive(archive, "my-host", "my-descr", self.config)
            self.assertEqual(ret["state"], "done")
            self.assertEqual(archive in ret["path"] and job_id in ret["path"], True) 
            

