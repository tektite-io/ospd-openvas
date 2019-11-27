# -*- coding: utf-8 -*-
# Copyright (C) 2018 Greenbone Networks GmbH
#
# SPDX-License-Identifier: GPL-2.0-or-later
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA

""" Provide functions to handle NVT Info Cache. """

import logging
import subprocess

from typing import List, Dict, Optional

from pkg_resources import parse_version

from ospd_openvas.db import NVT_META_FIELDS, RedisCtx
from ospd_openvas.errors import OspdOpenvasError


logger = logging.getLogger(__name__)

LIST_FIRST_POS = 0
LIST_LAST_POS = -1

SUPPORTED_NVTICACHE_VERSIONS = ('20.4',)


class NVTICache(object):

    QOD_TYPES = {
        'exploit': '100',
        'remote_vul': '99',
        'remote_app': '98',
        'package': '97',
        'registry': '97',
        'remote_active': '95',
        'remote_banner': '80',
        'executable_version': '80',
        'remote_analysis': '70',
        'remote_probe': '50',
        'remote_banner_unreliable': '30',
        'executable_version_unreliable': '30',
        'general_note': '1',
        'default': '70',
    }

    def __init__(self, openvas_db):
        self._openvas_db = openvas_db
        self._nvti_cache_name = None

    def _get_nvti_cache_name(self) -> str:
        if not self._nvti_cache_name:
            self._set_nvti_cache_name()

        return self._nvti_cache_name

    def _set_nvti_cache_name(self):
        """Set nvticache name"""
        try:
            result = subprocess.check_output(
                ['pkg-config', '--modversion', 'libgvm_util'],
                stderr=subprocess.STDOUT,
            )
        except (subprocess.CalledProcessError, PermissionError) as e:
            raise OspdOpenvasError(
                "Error setting nvticache. "
                "Not possible to get the installed "
                "gvm-libs version. %s" % e
            )

        version_string = str(result.decode('utf-8').rstrip())
        installed_lib = parse_version(version_string)

        for supported_item in SUPPORTED_NVTICACHE_VERSIONS:
            supported_lib = parse_version(supported_item)
            if (
                installed_lib >= supported_lib
                and installed_lib.base_version.split('.')[0]
                == supported_lib.base_version.split('.')[0]
            ):
                self._nvti_cache_name = "nvticache{}".format(version_string)

                return

        raise OspdOpenvasError(
            "Error setting nvticache. Incompatible nvticache "
            "version {}. Supported versions are {}.".format(
                version_string, ", ".join(SUPPORTED_NVTICACHE_VERSIONS)
            )
        )

    def get_redis_context(self) -> RedisCtx:
        """ Return the redix context for this nvti cache
        """
        return self._openvas_db.db_find(self._get_nvti_cache_name())

    def get_feed_version(self) -> str:
        """ Get feed version.
        """
        ctx = self.get_redis_context()
        return self._openvas_db.get_single_item(
            self._get_nvti_cache_name(), ctx=ctx
        )

    def get_oids(self) -> list:
        """ Get the list of NVT OIDs.
        Returns:
            A list of lists. Each single list contains the filename
            as first element and the oid as second one.
        """
        return self._openvas_db.get_elem_pattern_by_index('filename:*')

    def get_nvt_params(self, oid: str) -> Dict:
        """ Get NVT's preferences.
        Arguments:
            oid: OID of VT from which to get the parameters.
        Returns:
            A dictionary with preferences and timeout.
        """
        ctx = self._openvas_db.get_kb_context()
        prefs = self.get_nvt_prefs(ctx, oid)
        timeout = self.get_nvt_timeout(ctx, oid)

        if timeout is None:
            return None

        vt_params = {}
        if int(timeout) > 0:
            _param_id = '0'
            vt_params[_param_id] = dict()
            vt_params[_param_id]['id'] = _param_id
            vt_params[_param_id]['type'] = 'entry'
            vt_params[_param_id]['name'] = 'timeout'
            vt_params[_param_id]['description'] = 'Script Timeout'
            vt_params[_param_id]['default'] = timeout

        if prefs:
            for nvt_pref in prefs:
                elem = nvt_pref.split('|||')
                _param_id = elem[0]
                vt_params[_param_id] = dict()
                vt_params[_param_id]['id'] = _param_id
                vt_params[_param_id]['type'] = elem[2]
                vt_params[_param_id]['name'] = elem[1].strip()
                vt_params[_param_id]['description'] = 'Description'
                if elem[2]:
                    vt_params[_param_id]['default'] = elem[3]
                else:
                    vt_params[_param_id]['default'] = ''

        return vt_params

    @staticmethod
    def _parse_metadata_tags(tags_str: str, oid: str) -> Dict:
        """ Parse a string with multiple tags.

        Arguments:
            tags_str: String with tags separated by `|`.
            oid: VT OID. Only used for logging in error case.

        Returns:
            A dictionary with the tags.
        """
        tags_dict = dict()
        tags = tags_str.split('|')
        for tag in tags:
            try:
                _tag, _value = tag.split('=', 1)
            except ValueError:
                logger.error('Tag %s in %s has no value.', tag, oid)
                continue
            tags_dict[_tag] = _value

        return tags_dict

    def get_nvt_metadata(self, oid: str) -> Optional[Dict]:
        """ Get a full NVT. Returns an XML tree with the NVT metadata.
        Arguments:
            oid: OID of VT from which to get the metadata.
        Returns:
            A dictonary with the VT metadata.
        """
        ctx = self._openvas_db.get_kb_context()
        resp = self._openvas_db.get_list_item(
            "nvt:%s" % oid,
            ctx=ctx,
            start=NVT_META_FIELDS.index("NVT_FILENAME_POS"),
            end=NVT_META_FIELDS.index("NVT_NAME_POS"),
        )

        if not isinstance(resp, list) or len(resp) == 0:
            return None

        subelem = [
            'filename',
            'required_keys',
            'mandatory_keys',
            'excluded_keys',
            'required_udp_ports',
            'required_ports',
            'dependencies',
            'tag',
            'cve',
            'bid',
            'xref',
            'category',
            'timeout',
            'family',
            'name',
        ]

        custom = dict()
        for child, res in zip(subelem, resp):
            if child not in ['cve', 'bid', 'xref', 'tag'] and res:
                custom[child] = res
            elif child == 'tag':
                custom.update(self._parse_metadata_tags(res, oid))

        return custom

    def get_nvt_refs(self, oid: str) -> Optional[Dict]:
        """ Get a full NVT.
        Arguments:
            oid: OID of VT from which to get the VT references.
        Returns:
            A dictionary with the VT references.
        """
        ctx = self._openvas_db.get_kb_context()
        resp = self._openvas_db.get_list_item(
            "nvt:%s" % oid,
            ctx=ctx,
            start=NVT_META_FIELDS.index("NVT_CVES_POS"),
            end=NVT_META_FIELDS.index("NVT_XREFS_POS"),
        )

        if not isinstance(resp, list) or len(resp) == 0:
            return None

        subelem = ['cve', 'bid', 'xref']

        refs = dict()
        for child, res in zip(subelem, resp):
            refs[child] = res.split(", ")

        return refs

    def get_nvt_prefs(self, ctx: RedisCtx, oid: str) -> Optional[List]:
        """ Get NVT preferences.
        Arguments:
            ctx: Redis context to be used.
            oid: OID of VT from which to get the VT preferences.
        Returns:
            A list with the VT preferences.
        """
        key = 'oid:%s:prefs' % oid
        prefs = self._openvas_db.get_list_item(key, ctx=ctx)
        return prefs

    def get_nvt_timeout(self, ctx: RedisCtx, oid: str) -> str:
        """ Get NVT timeout
        Arguments:
            ctx: Redis context to be used.
            oid: OID of VT from which to get the script timeout.
        Returns:
            The timeout.
        """
        timeout = self._openvas_db.get_single_item(
            'nvt:%s' % oid,
            ctx=ctx,
            index=NVT_META_FIELDS.index("NVT_TIMEOUT_POS"),
        )

        return timeout

    def get_nvt_tag(self, ctx: RedisCtx, oid: str) -> Dict:
        """ Get Tags of the given OID.
        Arguments:
            ctx: Redis context to be used.
            oid: OID of VT from which to get the VT tags.
        Returns:
            A dictionary with the VT tags.
        """
        tag = self._openvas_db.get_single_item(
            'nvt:%s' % oid, ctx=ctx, index=NVT_META_FIELDS.index('NVT_TAGS_POS')
        )
        tags = tag.split('|')

        return dict([item.split('=', 1) for item in tags])
