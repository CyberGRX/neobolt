#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright (c) 2002-2019 "Neo4j,"
# Neo4j Sweden AB [http://neo4j.com]
#
# This file is part of Neo4j.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from unittest import TestCase

from neobolt.routing import READ_ACCESS, WRITE_ACCESS, RoutingProtocolError
from neobolt.impl.python.routing import RoutingTable


VALID_ROUTING_RECORD = {
    "ttl": 300,
    "servers": [
        {"role": "ROUTE", "addresses": ["127.0.0.1:9001", "127.0.0.1:9002", "127.0.0.1:9003"]},
        {"role": "READ", "addresses": ["127.0.0.1:9004", "127.0.0.1:9005"]},
        {"role": "WRITE", "addresses": ["127.0.0.1:9006"]},
    ],
}

VALID_ROUTING_RECORD_WITH_EXTRA_ROLE = {
    "ttl": 300,
    "servers": [
        {"role": "ROUTE", "addresses": ["127.0.0.1:9001", "127.0.0.1:9002", "127.0.0.1:9003"]},
        {"role": "READ", "addresses": ["127.0.0.1:9004", "127.0.0.1:9005"]},
        {"role": "WRITE", "addresses": ["127.0.0.1:9006"]},
        {"role": "MAGIC", "addresses": ["127.0.0.1:9007"]},
    ],
}

INVALID_ROUTING_RECORD = {
    "X": 1,
}


class RoutingTableConstructionTestCase(TestCase):
    def test_should_be_initially_stale(self):
        table = RoutingTable()
        assert not table.is_fresh(READ_ACCESS)
        assert not table.is_fresh(WRITE_ACCESS)


class RoutingTableParseRoutingInfoTestCase(TestCase):
    def test_should_return_routing_table_on_valid_record(self):
        table = RoutingTable.parse_routing_info([VALID_ROUTING_RECORD])
        assert table.routers == {('127.0.0.1', 9001), ('127.0.0.1', 9002), ('127.0.0.1', 9003)}
        assert table.readers == {('127.0.0.1', 9004), ('127.0.0.1', 9005)}
        assert table.writers == {('127.0.0.1', 9006)}
        assert table.ttl == 300

    def test_should_return_routing_table_on_valid_record_with_extra_role(self):
        table = RoutingTable.parse_routing_info([VALID_ROUTING_RECORD_WITH_EXTRA_ROLE])
        assert table.routers == {('127.0.0.1', 9001), ('127.0.0.1', 9002), ('127.0.0.1', 9003)}
        assert table.readers == {('127.0.0.1', 9004), ('127.0.0.1', 9005)}
        assert table.writers == {('127.0.0.1', 9006)}
        assert table.ttl == 300

    def test_should_fail_on_invalid_record(self):
        with self.assertRaises(RoutingProtocolError):
            _ = RoutingTable.parse_routing_info([INVALID_ROUTING_RECORD])

    def test_should_fail_on_zero_records(self):
        with self.assertRaises(RoutingProtocolError):
            _ = RoutingTable.parse_routing_info([])

    def test_should_fail_on_multiple_records(self):
        with self.assertRaises(RoutingProtocolError):
            _ = RoutingTable.parse_routing_info([VALID_ROUTING_RECORD, VALID_ROUTING_RECORD])


class RoutingTableServersTestCase(TestCase):
    def test_should_return_all_distinct_servers_in_routing_table(self):
        routing_table = {
            "ttl": 300,
            "servers": [
                {"role": "ROUTE", "addresses": ["127.0.0.1:9001", "127.0.0.1:9002", "127.0.0.1:9003"]},
                {"role": "READ", "addresses": ["127.0.0.1:9001", "127.0.0.1:9005"]},
                {"role": "WRITE", "addresses": ["127.0.0.1:9002"]},
            ],
        }
        table = RoutingTable.parse_routing_info([routing_table])
        assert table.servers() == {('127.0.0.1', 9001), ('127.0.0.1', 9002), ('127.0.0.1', 9003), ('127.0.0.1', 9005)}


class RoutingTableFreshnessTestCase(TestCase):
    def test_should_be_fresh_after_update(self):
        table = RoutingTable.parse_routing_info([VALID_ROUTING_RECORD])
        assert table.is_fresh(READ_ACCESS)
        assert table.is_fresh(WRITE_ACCESS)

    def test_should_become_stale_on_expiry(self):
        table = RoutingTable.parse_routing_info([VALID_ROUTING_RECORD])
        table.ttl = 0
        assert not table.is_fresh(READ_ACCESS)
        assert not table.is_fresh(WRITE_ACCESS)

    def test_should_become_stale_if_no_readers(self):
        table = RoutingTable.parse_routing_info([VALID_ROUTING_RECORD])
        table.readers.clear()
        assert not table.is_fresh(READ_ACCESS)
        assert table.is_fresh(WRITE_ACCESS)

    def test_should_become_stale_if_no_writers(self):
        table = RoutingTable.parse_routing_info([VALID_ROUTING_RECORD])
        table.writers.clear()
        assert table.is_fresh(READ_ACCESS)
        assert not table.is_fresh(WRITE_ACCESS)


class RoutingTableUpdateTestCase(TestCase):
    def setUp(self):
        self.table = RoutingTable(
            [("192.168.1.1", 7687), ("192.168.1.2", 7687)], [("192.168.1.3", 7687)], [], 0)
        self.new_table = RoutingTable(
            [("127.0.0.1", 9001), ("127.0.0.1", 9002), ("127.0.0.1", 9003)],
            [("127.0.0.1", 9004), ("127.0.0.1", 9005)], [("127.0.0.1", 9006)], 300)

    def test_update_should_replace_routers(self):
        self.table.update(self.new_table)
        assert self.table.routers == {("127.0.0.1", 9001), ("127.0.0.1", 9002), ("127.0.0.1", 9003)}

    def test_update_should_replace_readers(self):
        self.table.update(self.new_table)
        assert self.table.readers == {("127.0.0.1", 9004), ("127.0.0.1", 9005)}

    def test_update_should_replace_writers(self):
        self.table.update(self.new_table)
        assert self.table.writers == {("127.0.0.1", 9006)}

    def test_update_should_replace_ttl(self):
        self.table.update(self.new_table)
        assert self.table.ttl == 300
