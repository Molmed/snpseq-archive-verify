import unittest
import unittest.mock as mock
import yaml

from archive_verify.pdc_client import PdcClient


class TestPdcClient(unittest.TestCase):

    def setUp(self):
        with open("tests/test_config.yaml") as config:
            self.config = yaml.safe_load(config)

    def getPdcClient(self):
        return PdcClient("archive", "path", "descr", "1234", self.config)

    # Test with whitelisted warnings
    def test_dsmc_whitelist_ok(self):
        exit_code = 8
        whitelist = ["ANS2250W", "ANS5000W"]
        output = "TEST\nOUTPUT\nWARNING****************\nSEE ANS2250W FOR MORE INFO\nANS2250E\n"
        ret = PdcClient._parse_dsmc_return_code(exit_code, output, whitelist)
        self.assertEqual(ret, True)

    # Test with non-whitelisted warnings
    def test_dsmc_whitelist_not_ok(self):
        exit_code = 8
        whitelist = ["ANS2250W", "ANS5000W"]
        output = "FOOBAR TEST OKEJ\nWARNING ERROR ANS221E TEST\n*** ANS5050W\n"
        ret = PdcClient._parse_dsmc_return_code(exit_code, output, whitelist)
        self.assertEqual(ret, False)

    # Test with non-warning exit code
    def test_dsmc_unknown_exit_code(self):
        exit_code = 10
        whitelist = ["FOO", "BAR"]
        output = "FOO\nBAR\OK\n"
        ret = PdcClient._parse_dsmc_return_code(exit_code, output, whitelist)
        self.assertEqual(ret, False)

    # Check when dsmc returns 0
    @mock.patch('subprocess.Popen')
    def test_download_from_pdc_ok(self, mock_popen):
        mock_popen.return_value.returncode = 0
        mock_popen.return_value.communicate.return_value = ("foobar", '')
        ret = self.getPdcClient().download()
        self.assertEqual(ret, True)

    # Check when dsmc returns != 0
    def test_download_from_pdc_with_ok_warning(self):
        exp_ret = "33232"

        with mock.patch('subprocess.Popen') as mock_popen, mock.patch(
                'archive_verify.pdc_client.PdcClient._parse_dsmc_return_code') as mock_parse_dsmc:
            mock_popen.return_value.returncode = 42
            mock_popen.return_value.communicate.return_value = ("foobar", '')
            mock_parse_dsmc.return_value = exp_ret
            ret = self.getPdcClient().download()
            self.assertEqual(ret, exp_ret)

    def test_cleanup(self):
        with mock.patch('shutil.rmtree') as mock_rmtree:
            self.getPdcClient().cleanup()
            mock_rmtree.assert_called_with("data/verify/archive_1234")

    def test_dsmc_args(self):
        # ensure the default arguments are returned properly
        client = self.getPdcClient()
        base_args = f"-subdir='yes' -description='{client.archive_pdc_description}'"
        obs_args = client.dsmc_args()
        self.assertEqual(obs_args.split(" "), base_args.split(" "))

        # ensure extra arguments are added properly
        self.config["dsmc_extra_args"] = {
            "extra_key_1": "extra_val_1",
            "extra_key_2": "extra_val_2",
            "extra_key_3": None}
        client = self.getPdcClient()
        exp_args = f"{base_args} -extra_key_1='extra_val_1' -extra_key_2='extra_val_2' -extra_key_3"
        obs_args = client.dsmc_args()
        self.assertEqual(obs_args.split(" "), exp_args.split(" "))

        # ensure extra arguments override default arguments
        self.config["dsmc_extra_args"] = {
            "extra_key_1": "extra_val_1",
            "subdir": "no"}
        client = self.getPdcClient()
        exp_args = f"-subdir='no' -description='{client.archive_pdc_description}' " \
                   f"-extra_key_1='extra_val_1'"
        obs_args = client.dsmc_args()
        self.assertEqual(obs_args.split(" "), exp_args.split(" "))
