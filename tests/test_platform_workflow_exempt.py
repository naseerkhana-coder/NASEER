"""Platform admin modules bypass approval workflow."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from workflow_service import (
    RECORD_APPROVED,
    STATUS_APPROVED,
    create_approval_request,
    initial_workflow_after_save,
    is_platform_admin_module,
    route_exempt_from_workflow,
)


class PlatformWorkflowExemptTests(unittest.TestCase):
    def test_platform_module_ids(self):
        self.assertTrue(is_platform_admin_module("customer_master"))
        self.assertTrue(is_platform_admin_module("platform_settings"))
        self.assertFalse(is_platform_admin_module("boq"))

    def test_initial_workflow_immediate_for_platform(self):
        wf, stage, record = initial_workflow_after_save(None, "customer_master")
        self.assertEqual(wf, STATUS_APPROVED)
        self.assertEqual(stage, "completed")
        self.assertEqual(record, RECORD_APPROVED)

    def test_create_approval_request_skipped_for_platform(self):
        self.assertIsNone(
            create_approval_request(
                None,
                "license_master",
                1,
                "erp_licenses",
                "admin",
                user_id=1,
            )
        )

    def test_route_exempt_endpoints(self):
        self.assertTrue(route_exempt_from_workflow("erp_admin_customers"))
        self.assertFalse(route_exempt_from_workflow("boq_management"))


if __name__ == "__main__":
    unittest.main()
