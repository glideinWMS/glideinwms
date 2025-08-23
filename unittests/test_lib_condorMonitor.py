#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2009 Fermi Research Alliance, LLC
# SPDX-License-Identifier: Apache-2.0

"""This module implements classes to query the condor daemons and manipulate the results
Please notice that it also converts \" into "
"""
import os
import unittest

# from itertools import groupby
# from unittest import mock
from unittest.mock import MagicMock, patch

from glideinwms.lib.condorMonitor import (  # CondorStatus,
    complete_format_list,
    CondorQ,
    condorq_attrs,
    CondorQLite,
    CondorQuery,
    doNestedGroup,
    NestedGroup,
    NoneDiskCache,
    PBError,
    QueryError,
    xml2list_end_element,
    xml2list_start_element,
)

# import xmlrunner

# import glideinwms
# import glideinwms.lib.condorMonitor as condorMonitor


os.environ["CONDOR_CONFIG"] = "fixtures/frontend/vofrontend/frontend.condor-config"


class TestQueryError(unittest.TestCase):
    def test_query_error_inheritance(self):
        # QueryError should be a subclass of RuntimeError
        self.assertTrue(issubclass(QueryError, RuntimeError))

    def test_query_error_message(self):
        msg = "Something went wrong"
        err = QueryError(msg)
        self.assertIsInstance(err, RuntimeError)
        self.assertEqual(str(err), msg)

    def test_query_error_raises(self):
        # It should be raisable and catchable as RuntimeError
        with self.assertRaises(RuntimeError) as context:
            raise QueryError("test error")
        self.assertEqual(str(context.exception), "test error")


class TestPBError(unittest.TestCase):
    def test_pberror_inheritance(self):
        self.assertTrue(issubclass(PBError, RuntimeError))

    def test_pberror_message(self):
        msg = "HTCondor binding error"
        err = PBError(msg)
        self.assertIsInstance(err, RuntimeError)
        self.assertEqual(str(err), msg)

    def test_pberror_can_be_raised_and_caught(self):
        with self.assertRaises(RuntimeError) as context:
            raise PBError("bad things happened")
        self.assertEqual(str(context.exception), "bad things happened")


class TestNoneDiskCache(unittest.TestCase):
    def setUp(self):
        self.cache = NoneDiskCache()

    def test_get_always_returns_none(self):
        self.assertIsNone(self.cache.get("some_id"))
        self.assertIsNone(self.cache.get(None))
        self.assertIsNone(self.cache.get(1234))

    def test_save_always_returns_none(self):
        self.assertIsNone(self.cache.save("some_id", {"a": 1}))
        self.assertIsNone(self.cache.save(None, None))
        self.assertIsNone(self.cache.save("key", "value"))


class TestCondorqAttrs(unittest.TestCase):
    @patch("condorMonitor.xml2list")
    @patch("condorMonitor.condorExe")
    def test_condorq_attrs(self, mock_condorExe, mock_xml2list):
        # Setup mocks
        mock_condorExe.exe_cmd.return_value = [
            '<?xml version="1.0"?>',
            "<c>",
            '<a n="Owner">user1</a>',
            "</c>",
            '<?xml version="1.0"?>',
            "<c>",
            '<a n="Owner">user2</a>',
            "</c>",
        ]
        # Each xml2list call returns a different parsed list
        mock_xml2list.side_effect = [
            [{"Owner": "user1"}],
            [{"Owner": "user2"}],
        ]
        q_constraint = "ClusterId==1234"
        attribute_list = ["Owner"]
        result = condorq_attrs(q_constraint, attribute_list)

        # Should return a flattened list of all classads from both XMLs
        self.assertEqual(result, [{"Owner": "user1"}, {"Owner": "user2"}])

        # Check that exe_cmd was called with correct arguments
        expected_attr_str = " -attr Owner"
        expected_cmd = f"-g -l {expected_attr_str} -xml -constraint '{q_constraint}'"
        mock_condorExe.exe_cmd.assert_called_once_with("condor_q", expected_cmd)

        # xml2list should be called for each xml chunk
        self.assertEqual(mock_xml2list.call_count, 2)
        # Each call gets a list of lines per XML header
        args_list = mock_xml2list.call_args_list
        for call_args in args_list:
            self.assertIsInstance(call_args[0][0], list)


class TestCondorQuery(unittest.TestCase):
    @patch("condorMonitor.copy.deepcopy")
    @patch("condorMonitor.condorSecurity")
    def test_init_no_pool_no_security(self, mock_condorSecurity, mock_deepcopy):
        # When pool_name is None, pool_str should be empty
        # When security_obj is None, uses ProtoRequest()
        mock_proto = MagicMock()
        mock_condorSecurity.ProtoRequest.return_value = mock_proto

        q = CondorQuery("condor_status", "-startd", "Name")
        self.assertEqual(q.exe_name, "condor_status")
        self.assertEqual(q.resource_str, "-startd")
        self.assertEqual(q.group_attribute, "Name")
        self.assertEqual(q.pool_name, None)
        self.assertEqual(q.pool_str, "")
        self.assertEqual(q.env, {})
        self.assertIs(q.security_obj, mock_proto)
        mock_condorSecurity.ProtoRequest.assert_called_once()

    @patch("condorMonitor.copy.deepcopy")
    @patch("condorMonitor.condorSecurity")
    def test_init_with_pool_with_security(self, mock_condorSecurity, mock_deepcopy):
        # When pool_name is not None, pool_str is set accordingly
        # When security_obj is provided and has_saved_state is False, deepcopy is called
        mock_sec = MagicMock()
        mock_sec.has_saved_state.return_value = False
        mock_proto = MagicMock()
        mock_condorSecurity.ProtoRequest.return_value = mock_proto
        mock_deepcopy.return_value = "cloned_sec"

        q = CondorQuery("condor_q", "-schedd", "ClusterId", pool_name="testpool", security_obj=mock_sec, env={"K": "V"})
        self.assertEqual(q.pool_str, "-pool testpool")
        self.assertEqual(q.security_obj, "cloned_sec")
        mock_deepcopy.assert_called_once_with(mock_sec)

    @patch("condorMonitor.copy.deepcopy")
    @patch("condorMonitor.condorSecurity")
    def test_init_with_security_with_saved_state(self, mock_condorSecurity, mock_deepcopy):
        # If has_saved_state returns True, raises RuntimeError
        mock_sec = MagicMock()
        mock_sec.has_saved_state.return_value = True
        with self.assertRaises(RuntimeError):
            CondorQuery("condor_q", "-schedd", "ClusterId", pool_name="pool", security_obj=mock_sec)
        mock_deepcopy.assert_not_called()


class TestCondorQ(unittest.TestCase):
    @patch("condorMonitor.CondorQuery.__init__")
    def test_init_with_lookup_cache(self, mock_super_init):
        mock_cache = MagicMock()
        mock_cache.getScheddId.return_value = ("-name myschedd ", {"SOMEENV": "VAL"})

        q = CondorQ(schedd_name="myschedd", pool_name="mypool", security_obj="SEC", schedd_lookup_cache=mock_cache)

        # Ensures super().__init__ was called with the expected arguments
        mock_super_init.assert_called_once_with(
            "condor_q", "-name myschedd ", ["ClusterId", "ProcId"], "mypool", "SEC", {"SOMEENV": "VAL"}
        )
        # The instance keeps the schedd_name and pool_name
        self.assertEqual(q.schedd_name, "myschedd")

    @patch("condorMonitor.CondorQuery.__init__")
    def test_init_default_cache(self, mock_super_init):
        # If schedd_lookup_cache is None, should default to NoneScheddCache
        # We'll patch NoneScheddCache as well for controlled output
        with patch("condorMonitor.NoneScheddCache") as MockCache:
            instance = MockCache.return_value
            instance.getScheddId.return_value = ("", {})
            q = CondorQ(schedd_name=None, pool_name=None, security_obj=None, schedd_lookup_cache=None)
            mock_super_init.assert_called_once_with("condor_q", "", ["ClusterId", "ProcId"], None, None, {})
            self.assertIsNone(q.schedd_name)


class TestCondorStatus(unittest.TestCase):
    @patch("condorMonitor.CondorQuery.__init__")
    def test_init_with_subsystem(self, mock_super_init):
        # status = CondorStatus(subsystem_name="startd", pool_name="poolx", security_obj="SEC")
        mock_super_init.assert_called_once_with("condor_status", "-startd", "Name", "poolx", "SEC", {})

    @patch("condorMonitor.CondorQuery.__init__")
    def test_init_default(self, mock_super_init):
        # status = CondorStatus()
        mock_super_init.assert_called_once_with("condor_status", "", "Name", None, None, {})


class TestNestedGroup(unittest.TestCase):
    @patch("condorMonitor.doNestedGroup")
    def test_init_and_fetch(self, mock_doNestedGroup):
        # Mock a fake query object with .fetch()
        mock_query = MagicMock()
        mock_query.fetch.return_value = {"a": {"x": 1}, "b": {"x": 2}}

        # Define dummy group_key_func and group_element_func
        def group_key_func(val):
            return val["x"] % 2  # group by even/odd

        def group_element_func(items):
            return {"sum": sum(k for k, v in items)}

        # Setup doNestedGroup mock to return a sentinel value
        mock_doNestedGroup.return_value = {"dummy": 42}

        # Create NestedGroup
        ng = NestedGroup(mock_query, group_key_func, group_element_func)

        # .fetch() should call doNestedGroup with the query's .fetch() result
        result = ng.fetch()
        mock_doNestedGroup.assert_called_once_with({"a": {"x": 1}, "b": {"x": 2}}, group_key_func, group_element_func)
        self.assertEqual(result, {"dummy": 42})

    @patch("condorMonitor.doNestedGroup")
    def test_default_group_element_func(self, mock_doNestedGroup):
        mock_query = MagicMock()
        mock_query.fetch.return_value = {"z": {"x": 0}}
        # When group_element_func is None, should use dict
        ng = NestedGroup(mock_query, lambda v: "key")
        ng.fetch()
        args = mock_doNestedGroup.call_args[0]
        # The last argument should be None or dict
        # If your code explicitly passes None, you can check that
        # If it passes dict by default, check accordingly
        # Here, we expect None to get passed as group_element_func if not supplied
        self.assertTrue(args[2] is None or args[2] is dict)


class TestCompleteFormatList(unittest.TestCase):
    def test_adds_missing_required_elements(self):
        in_list = [("ClusterId", "i"), ("ProcId", "i")]
        req_list = [("Owner", "s"), ("ClusterId", "i")]
        result = complete_format_list(in_list, req_list)
        # Owner should be appended, ClusterId should not duplicate
        self.assertIn(("Owner", "s"), result)
        self.assertEqual(result.count(("ClusterId", "i")), 1)
        self.assertEqual(len(result), 3)

    def test_no_required_elements(self):
        in_list = [("ClusterId", "i")]
        req_list = []
        result = complete_format_list(in_list, req_list)
        self.assertEqual(result, in_list)

    def test_empty_input_list(self):
        in_list = []
        req_list = [("Owner", "s")]
        result = complete_format_list(in_list, req_list)
        self.assertEqual(result, [("Owner", "s")])

    def test_both_empty(self):
        self.assertEqual(complete_format_list([], []), [])

    def test_duplicate_required_elements(self):
        in_list = [("ClusterId", "i")]
        req_list = [("ClusterId", "i"), ("ClusterId", "i")]
        result = complete_format_list(in_list, req_list)
        # Should only have one ClusterId entry
        self.assertEqual(result, [("ClusterId", "i")])


class TestXml2ListStartElement(unittest.TestCase):
    def setUp(self):
        # Patch globals in the function's module namespace
        global_vars = {
            "xml2list_data": [],
            "xml2list_inclassad": None,
            "xml2list_inattr": None,
            "xml2list_intype": None,
        }
        for k, v in global_vars.items():
            setattr(__import__("condorMonitor"), k, v)

    def get_globals(self):
        mod = __import__("condorMonitor")
        return {
            "xml2list_data": getattr(mod, "xml2list_data"),
            "xml2list_inclassad": getattr(mod, "xml2list_inclassad"),
            "xml2list_inattr": getattr(mod, "xml2list_inattr"),
            "xml2list_intype": getattr(mod, "xml2list_intype"),
        }

    def test_c_element(self):
        xml2list_start_element("c", {})
        self.assertEqual(self.get_globals()["xml2list_inclassad"], {})

    def test_a_element_sets_attr_and_type(self):
        xml2list_start_element("a", {"n": "SomeAttr"})
        g = self.get_globals()
        self.assertEqual(g["xml2list_inattr"], {"name": "SomeAttr", "val": ""})
        self.assertEqual(g["xml2list_intype"], "s")

    def test_i_element(self):
        xml2list_start_element("i", {})
        self.assertEqual(self.get_globals()["xml2list_intype"], "i")

    def test_r_element(self):
        xml2list_start_element("r", {})
        self.assertEqual(self.get_globals()["xml2list_intype"], "r")

    def test_b_element_with_v(self):
        xml2list_start_element("a", {"n": "boolAttr"})  # set inattr
        xml2list_start_element("b", {"v": "T"})
        self.assertEqual(self.get_globals()["xml2list_intype"], "b")
        self.assertTrue(self.get_globals()["xml2list_inattr"]["val"])

    def test_b_element_without_v(self):
        xml2list_start_element("a", {"n": "boolAttr"})  # set inattr
        xml2list_start_element("b", {})
        self.assertIsNone(self.get_globals()["xml2list_inattr"]["val"])

    def test_un_element(self):
        xml2list_start_element("a", {"n": "unknown"})
        xml2list_start_element("un", {})
        self.assertEqual(self.get_globals()["xml2list_intype"], "un")
        self.assertIsNone(self.get_globals()["xml2list_inattr"]["val"])

    def test_unsupported_element_raises(self):
        with self.assertRaises(TypeError):
            xml2list_start_element("not_supported", {})

    def test_s_and_e_and_classads_do_nothing(self):
        # These should not change globals or raise
        before = self.get_globals()
        xml2list_start_element("s", {})
        xml2list_start_element("e", {})
        xml2list_start_element("classads", {})
        after = self.get_globals()
        self.assertEqual(before, after)


class TestXml2ListEndElement(unittest.TestCase):
    def setUp(self):
        # Patch the globals in the module's namespace
        mod = __import__("condorMonitor")
        mod.xml2list_data = []
        mod.xml2list_inclassad = None
        mod.xml2list_inattr = None
        mod.xml2list_intype = None

    def get_globals(self):
        mod = __import__("condorMonitor")
        return {
            "xml2list_data": getattr(mod, "xml2list_data"),
            "xml2list_inclassad": getattr(mod, "xml2list_inclassad"),
            "xml2list_inattr": getattr(mod, "xml2list_inattr"),
            "xml2list_intype": getattr(mod, "xml2list_intype"),
        }

    def test_end_c_appends_inclassad(self):
        mod = __import__("condorMonitor")
        mod.xml2list_inclassad = {"Owner": "user1"}
        xml2list_end_element("c")
        self.assertEqual(mod.xml2list_data, [{"Owner": "user1"}])
        self.assertIsNone(mod.xml2list_inclassad)

    def test_end_a_adds_inattr_to_inclassad(self):
        mod = __import__("condorMonitor")
        mod.xml2list_inclassad = {}
        mod.xml2list_inattr = {"name": "ClusterId", "val": 1001}
        xml2list_end_element("a")
        self.assertEqual(mod.xml2list_inclassad, {"ClusterId": 1001})
        self.assertIsNone(mod.xml2list_inattr)

    def test_end_i_b_un_r_resets_intype(self):
        mod = __import__("condorMonitor")
        for typ in ["i", "b", "un", "r"]:
            mod.xml2list_intype = typ
            xml2list_end_element(typ)
            self.assertEqual(mod.xml2list_intype, "s")

    def test_end_s_e_and_classads_do_nothing(self):
        before = self.get_globals()
        xml2list_end_element("s")
        xml2list_end_element("e")
        xml2list_end_element("classads")
        after = self.get_globals()
        self.assertEqual(before, after)

    def test_unsupported_element_raises(self):
        with self.assertRaises(TypeError):
            xml2list_end_element("not_supported")


class TestDoNestedGroup(unittest.TestCase):
    def test_default_grouping(self):
        # Group by value's parity, no group_element_func
        data = {
            "a": {"v": 1},
            "b": {"v": 2},
            "c": {"v": 3},
        }
        # group_key_func = lambda d: d["v"] % 2
        # By default, outdata[k] = dict of (key, value) pairs in that group
        result = doNestedGroup(data, lambda d: d["v"] % 2)
        self.assertIn(0, result)
        self.assertIn(1, result)
        # Even group: only 'b'
        self.assertEqual(result[0], {"b": {"v": 2}})
        # Odd group: 'a' and 'c'
        self.assertEqual(result[1], {"a": {"v": 1}, "c": {"v": 3}})

    def test_custom_group_element_func(self):
        # Custom: just count number of items in group
        data = {"a": {"x": 5}, "b": {"x": 6}, "c": {"x": 5}}
        # group_key_func = lambda d: d["x"]
        # group_element_func = lambda group: {"count": len(group)}
        result = doNestedGroup(data, lambda d: d["x"], lambda group: {"count": len(group)})
        # x=5: two elements, x=6: one element
        self.assertEqual(
            result,
            {
                5: {"count": 2},
                6: {"count": 1},
            },
        )

    def test_empty_input(self):
        result = doNestedGroup({}, lambda x: "whatever")
        self.assertEqual(result, {})

    def test_none_group_element_func_is_dict(self):
        data = {"k": {"foo": "bar"}}
        result = doNestedGroup(data, lambda d: 1)
        # Should be a dict of the single element, with its original key
        self.assertEqual(result, {1: {"k": {"foo": "bar"}}})


class TestCondorQLite(unittest.TestCase):
    @patch("condorMonitor.CondorQuery.__init__")
    def test_init_with_custom_cache(self, mock_super_init):
        mock_cache = MagicMock()
        mock_cache.getScheddId.return_value = ("-name test ", {"CUSTOM": "YES"})
        cql = CondorQLite(schedd_name="test", pool_name="poolx", security_obj="SEC", schedd_lookup_cache=mock_cache)
        # The parent __init__ should be called with the right arguments
        mock_super_init.assert_called_once_with(
            "condor_q", "-name test ", "ClusterId", "poolx", "SEC", {"CUSTOM": "YES"}
        )
        self.assertEqual(cql.schedd_name, "test")

    @patch("condorMonitor.CondorQuery.__init__")
    def test_init_with_default_cache(self, mock_super_init):
        # If schedd_lookup_cache is None, it should default to NoneScheddCache
        with patch("condorMonitor.NoneScheddCache") as MockCache:
            inst = MockCache.return_value
            inst.getScheddId.return_value = ("", {})
            cql = CondorQLite(schedd_name=None, pool_name=None, security_obj=None, schedd_lookup_cache=None)
            mock_super_init.assert_called_once_with("condor_q", "", "ClusterId", None, None, {})
            self.assertIsNone(cql.schedd_name)


if __name__ == "__main__":
    print("starting test")
    # unittest.main()
    print("after")
