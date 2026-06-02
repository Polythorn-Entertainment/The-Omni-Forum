from __future__ import annotations

import inspect
import unittest


class ApiRouteTableTests(unittest.TestCase):
    def test_api_route_table_matches_handler_methods(self) -> None:
        from app import ForumHandler
        from omniforum.api_routes import API_ROUTES

        missing = sorted({route.endpoint for route in API_ROUTES if not hasattr(ForumHandler, route.endpoint)})
        self.assertEqual([], missing)
        mismatches = []
        for route in API_ROUTES:
            params = [
                param
                for param in inspect.signature(getattr(ForumHandler, route.endpoint)).parameters.values()
                if param.kind in {param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD}
            ]
            required_count = len(route.args) + 1
            extra_required = [
                param.name for param in params[required_count:] if param.default is inspect.Parameter.empty
            ]
            if len(params) < required_count or extra_required:
                mismatches.append((route.method, route.pattern.pattern, route.endpoint, route.args))
        self.assertEqual([], mismatches)


if __name__ == "__main__":
    unittest.main()
