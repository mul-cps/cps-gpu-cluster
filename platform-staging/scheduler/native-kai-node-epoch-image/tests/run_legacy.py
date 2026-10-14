"""Run unchanged runtime fixtures; the one source-generator check runs separately.

Node507 never ships cps_compute.native_group_process; runtime uses the exact
vendored native_approval_process.py. The golden-source check is recorded against
the original dc72f653 source in reviewed7d on the host; nothing is injected into
the runtime namespace.
"""
import sys
import unittest
suite=unittest.TestSuite()
loader=unittest.defaultTestLoader
for name in ['test_native_approval_revision.ApprovalNodeTest','test_node_agent.EnrollmentTest']:
    suite.addTests(loader.loadTestsFromName(name))
import test_native_approval_publisher as publisher
for name in loader.getTestCaseNames(publisher.PublisherTests):
    if name!='test_observer_overlay_changes_only_import_adapter_and_is_pinned':
        suite.addTest(publisher.PublisherTests(name))
result=unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
