import copy
import mock
import unittest
import yaml

from archive_verify.workers import compare_md5sum, get_pdc_client, verify_archive


class TestWorkers(unittest.TestCase):
    def setUp(self):
        with open("tests/test_config.yaml") as config:
            self.config = yaml.load(config)

    def test_pdc_client_is_default(self):
        pdc_client = get_pdc_client(self.config)
        self.assertEqual(pdc_client.__name__, 'PdcClient')

    def test_pdc_client_selected(self):
        config = copy.copy(self.config)
        config['pdc_client'] = 'PdcClient'
        pdc_client = get_pdc_client(config)
        self.assertEqual(pdc_client.__name__, 'PdcClient')

    def test_mock_pdc_client_selected(self):
        config = copy.copy(self.config)
        config['pdc_client'] = 'MockPdcClient'
        pdc_client = get_pdc_client(config)
        self.assertEqual(pdc_client.__name__, 'MockPdcClient')

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
        with mock.patch('archive_verify.pdc_client.PdcClient.download') as mock_download, mock.patch('rq.get_current_job') as mock_job:
            job_id = "42-42-42-24-24-24"
            mock_download.return_value = False
            mock_job.return_value.id = job_id
            ret = verify_archive("my-archive", "my-host", "my-descr", self.config)
            self.assertEqual(ret["state"], "error")
            self.assertEqual(job_id in ret["path"], True)

    def test_verify_archive_verify_not_ok(self): 
        with mock.patch('archive_verify.pdc_client.PdcClient.download') as mock_download, mock.patch('rq.get_current_job') as mock_job, mock.patch('archive_verify.workers.compare_md5sum') as mock_md5sum:
            job_id = "24-24-24-24"
            archive = "my-archive-101"
            mock_download.return_value = True
            mock_job.return_value.id = job_id
            mock_md5sum.return_value = False
            ret = verify_archive(archive, "my-host", "my-descr", self.config)
            self.assertEqual(ret["state"], "error")
            self.assertEqual(archive in ret["path"], True)

    def test_verify_archive_verify_ok(self):
        with mock.patch('archive_verify.pdc_client.PdcClient.download') as mock_download, mock.patch('rq.get_current_job') as mock_job, mock.patch('archive_verify.workers.compare_md5sum') as mock_md5sum:
            job_id = "24-24-24-24"
            archive = "my-archive-101" 
            mock_download.return_value = True
            mock_job.return_value.id = job_id
            mock_md5sum.return_value = True
            ret = verify_archive(archive, "my-host", "my-descr", self.config)
            self.assertEqual(ret["state"], "done")
            self.assertEqual(archive in ret["path"] and job_id in ret["path"], True) 
            

