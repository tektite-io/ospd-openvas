# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2014-2023 Greenbone AG
#
# SPDX-License-Identifier: AGPL-3.0-or-later


# pylint: disable=unused-argument, protected-access, invalid-name

"""Unit Test for ospd-openvas"""

import logging

from unittest import TestCase
from unittest.mock import patch, Mock, PropertyMock
from pathlib import Path

from ospd_openvas.nvticache import NVTICache, NVTI_CACHE_NAME

from tests.helper import assert_called


@patch('ospd_openvas.nvticache.OpenvasDB')
class TestNVTICache(TestCase):
    @patch('ospd_openvas.db.MainDB')
    def setUp(self, MockMainDB):  # pylint: disable=arguments-differ
        self.db = MockMainDB()
        self.nvti = NVTICache(self.db)
        self.nvti._ctx = 'foo'

    def test_set_index(self, MockOpenvasDB):
        self.nvti._ctx = None

        MockOpenvasDB.find_database_by_pattern.return_value = ('foo', 22)

        ctx = self.nvti.ctx

        self.assertIsNotNone(ctx)
        self.assertEqual(ctx, 'foo')
        self.assertEqual(self.nvti.index, 22)

    def test_get_feed_version(self, MockOpenvasDB):
        MockOpenvasDB.get_single_item.return_value = '1234'

        resp = self.nvti.get_feed_version()

        self.assertEqual(resp, '1234')
        MockOpenvasDB.get_single_item.assert_called_with('foo', NVTI_CACHE_NAME)

    def test_get_feed_version_not_available(self, MockOpenvasDB):
        pmock = PropertyMock(return_value=123)
        type(self.db).max_database_index = pmock
        self.nvti._ctx = None

        MockOpenvasDB.find_database_by_pattern.return_value = (None, None)

        resp = self.nvti.get_feed_version()

        self.assertIsNone(resp)
        MockOpenvasDB.find_database_by_pattern.assert_called_with(
            NVTI_CACHE_NAME, 123
        )

    def test_get_oids(self, MockOpenvasDB):
        MockOpenvasDB.get_filenames_and_oids.return_value = [
            ('filename', 'oid')
        ]

        resp = self.nvti.get_oids()

        self.assertEqual([x for x in resp], [('filename', 'oid')])

    def test_parse_metadata_tag_missing_value(self, MockOpenvasDB):
        logging.Logger.error = Mock()

        tags = 'tag1'
        ret = (
            NVTICache._parse_metadata_tags(  # pylint: disable=protected-access
                tags, '1.2.3'
            )
        )

        self.assertEqual(ret, {})
        assert_called(logging.Logger.error)

    def test_parse_metadata_tag(self, MockOpenvasDB):
        tags = 'tag1=value1'
        ret = (
            NVTICache._parse_metadata_tags(  # pylint: disable=protected-access
                tags, '1.2.3'
            )
        )

        self.assertEqual(ret, {'tag1': 'value1'})

    def test_parse_metadata_tags(self, MockOpenvasDB):
        tags = 'tag1=value1|foo=bar'
        ret = (
            NVTICache._parse_metadata_tags(  # pylint: disable=protected-access
                tags, '1.2.3'
            )
        )

        self.assertEqual(ret, {'tag1': 'value1', 'foo': 'bar'})

    def test_get_nvt_params(self, MockOpenvasDB):
        prefs1 = ['1|||dns-fuzz.timelimit|||entry|||default']
        prefs2 = ['1|||dns-fuzz.timelimit|||entry|||']
        prefs3 = ['1|||dns-fuzz.timelimit|||entry']

        out_dict1 = {
            '1': {
                'id': '1',
                'type': 'entry',
                'default': 'default',
                'name': 'dns-fuzz.timelimit',
                'description': 'Description',
            },
        }

        out_dict2 = {
            '1': {
                'id': '1',
                'type': 'entry',
                'default': '',
                'name': 'dns-fuzz.timelimit',
                'description': 'Description',
            },
        }

        MockOpenvasDB.get_list_item.return_value = prefs1

        resp = self.nvti.get_nvt_params('1.2.3.4')
        self.assertEqual(resp, out_dict1)

        MockOpenvasDB.get_list_item.return_value = prefs2

        resp = self.nvti.get_nvt_params('1.2.3.4')
        self.assertEqual(resp, out_dict2)

        MockOpenvasDB.get_list_item.return_value = prefs3

        resp = self.nvti.get_nvt_params('1.2.3.4')
        self.assertEqual(resp, out_dict2)

    def test_get_nvt_metadata(self, MockOpenvasDB):
        metadata = [
            'mantis_detect.nasl',
            '',
            '',
            'Settings/disable_cgi_scanning',
            '',
            'Services/www, 80',
            'find_service.nasl, http_version.nasl',
            'cvss_base_vector=AV:N/AC:L/Au:N/C:N/I:N'
            '/A:N|last_modification=1533906565'
            '|creation_date=1237458156'
            '|summary=Detects the ins'
            'talled version of\n  Mantis a free popular web-based '
            'bugtracking system.\n\n  This script sends HTTP GET r'
            'equest and try to get the version from the\n  respons'
            'e, and sets the result in KB.|qod_type=remote_banner',
            '',
            '',
            'URL:http://www.mantisbt.org/',
            '3',
            'Product detection',
            'Mantis Detection',
        ]

        custom = {
            'category': '3',
            'creation_date': '1237458156',
            'cvss_base_vector': 'AV:N/AC:L/Au:N/C:N/I:N/A:N',
            'dependencies': 'find_service.nasl, http_version.nasl',
            'excluded_keys': 'Settings/disable_cgi_scanning',
            'family': 'Product detection',
            'filename': 'mantis_detect.nasl',
            'last_modification': ('1533906565'),
            'name': 'Mantis Detection',
            'qod_type': 'remote_banner',
            'refs': {'xref': ['URL:http://www.mantisbt.org/']},
            'required_ports': 'Services/www, 80',
            'summary': (
                'Detects the installed version of\n  Mantis a '
                'free popular web-based bugtracking system.\n'
                '\n  This script sends HTTP GET request and t'
                'ry to get the version from the\n  response, '
                'and sets the result in KB.'
            ),
            'vt_params': {
                '0': {
                    'id': '0',
                    'type': 'entry',
                    'name': 'timeout',
                    'description': 'Description',
                    'default': '10',
                },
                '1': {
                    'id': '1',
                    'type': 'entry',
                    'name': 'dns-fuzz.timelimit',
                    'description': 'Description',
                    'default': 'default',
                },
            },
        }

        prefs1 = [
            '0|||timeout|||entry|||10',
            '1|||dns-fuzz.timelimit|||entry|||default',
        ]

        MockOpenvasDB.get_list_item.side_effect = [metadata, prefs1]
        resp = self.nvti.get_nvt_metadata('1.2.3.4')
        self.maxDiff = None
        self.assertEqual(resp, custom)

    def test_get_nvt_metadata_fail(self, MockOpenvasDB):
        MockOpenvasDB.get_list_item.return_value = []

        resp = self.nvti.get_nvt_metadata('1.2.3.4')

        self.assertIsNone(resp)

    def test_get_nvt_refs(self, MockOpenvasDB):
        refs = ['', '', 'URL:http://www.mantisbt.org/']
        out_dict = {
            'cve': [''],
            'bid': [''],
            'xref': ['URL:http://www.mantisbt.org/'],
        }

        MockOpenvasDB.get_list_item.return_value = refs

        resp = self.nvti.get_nvt_refs('1.2.3.4')

        self.assertEqual(resp, out_dict)

    def test_get_nvt_refs_fail(self, MockOpenvasDB):
        MockOpenvasDB.get_list_item.return_value = []

        resp = self.nvti.get_nvt_refs('1.2.3.4')

        self.assertIsNone(resp)

    def test_get_nvt_prefs(self, MockOpenvasDB):
        prefs = ['dns-fuzz.timelimit|||entry|||default']

        MockOpenvasDB.get_list_item.return_value = prefs

        resp = self.nvti.get_nvt_prefs('1.2.3.4')

        self.assertEqual(resp, prefs)

    def test_get_nvt_tags(self, MockOpenvasDB):
        tag = (
            'last_modification=1533906565'
            '|creation_date=1517443741|cvss_bas'
            'e_vector=AV:N/AC:L/Au:N/C:P/I:P/A:P|solution_type=V'
            'endorFix|qod_type=package|affected=rubygems on Debi'
            'an Linux|solution_method=DebianAPTUpgrade'
        )

        out_dict = {
            'last_modification': '1533906565',
            'creation_date': '1517443741',
            'cvss_base_vector': 'AV:N/AC:L/Au:N/C:P/I:P/A:P',
            'solution_type': 'VendorFix',
            'qod_type': 'package',
            'affected': 'rubygems on Debian Linux',
            'solution_method': 'DebianAPTUpgrade',
        }

        MockOpenvasDB.get_single_item.return_value = tag

        resp = self.nvti.get_nvt_tags('1.2.3.4')

        self.assertEqual(out_dict, resp)

    def test_get_nvt_files_count(self, MockOpenvasDB):
        MockOpenvasDB.get_key_count.return_value = 20

        self.assertEqual(self.nvti.get_nvt_files_count(), 20)
        MockOpenvasDB.get_key_count.assert_called_with('foo', 'filename:*')

    def test_get_nvt_count(self, MockOpenvasDB):
        MockOpenvasDB.get_key_count.return_value = 20

        self.assertEqual(self.nvti.get_nvt_count(), 20)
        MockOpenvasDB.get_key_count.assert_called_with('foo', 'nvt:*')

    def test_flush(self, _MockOpenvasDB):
        self.nvti._ctx = Mock()

        self.nvti.flush()

        self.nvti._ctx.flushdb.assert_called_with()

    def test_add_vt(self, MockOpenvasDB):
        MockOpenvasDB.add_single_list = Mock()

        self.nvti.add_vt_to_cache(
            '1234',
            [
                'a',
                'b',
                'c',
                'd',
                'e',
                'f',
                'g',
                'h',
                'i',
                'j',
                'k',
                'l',
                'm',
                'n',
                'o',
            ],
        )
        MockOpenvasDB.add_single_list.assert_called_with(
            'foo',
            '1234',
            [
                'a',
                'b',
                'c',
                'd',
                'e',
                'f',
                'g',
                'h',
                'i',
                'j',
                'k',
                'l',
                'm',
                'n',
                'o',
            ],
        )

    def test_get_file_checksum(self, MockOpenvasDB):
        MockOpenvasDB.get_single_item.return_value = '123456'
        path = Path("/tmp/foo.csv")

        resp = self.nvti.get_file_checksum(path)

        self.assertEqual(resp, '123456')
        MockOpenvasDB.get_single_item.assert_called_with(
            'foo', "sha256sums:/tmp/foo.csv"
        )
