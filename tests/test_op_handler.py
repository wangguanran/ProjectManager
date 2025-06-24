import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from vprjcore.project import Project

class DummyArgs(dict):
    def pop(self, k, default=None):
        return super().pop(k, default)

def test_get_op_handler():
    args = DummyArgs({
        'operate': 'dummy',
        'project_name': 'dummy',
        'base': 'dummy',
    })
    prj = Project(args)
    op_handler = prj._get_op_handler()
    assert 'test_hello' in op_handler
    assert callable(op_handler['test_hello'])
    assert op_handler['test_hello']() == 'hello world' 