"""Shared rule-based intent detection helpers."""

NEGATED_TEST_PHRASES = (
    "without running tests",
    "do not run tests",
    "don't run tests",
    "no tests",
    "skip tests",
    "without pytest",
    "do not use pytest",
    "don't use pytest",
)

EXPLICIT_TEST_PHRASES = (
    "run tests",
    "run pytest",
    "execute tests",
    "test this",
    "run the test suite",
    "pytest",
    "failing test",
    "test failure",
)


def should_run_tests(user_request: str) -> bool:
    """Return True only when a request explicitly asks to run tests."""
    normalized_request = user_request.lower()
    if any(phrase in normalized_request for phrase in NEGATED_TEST_PHRASES):
        return False
    return any(phrase in normalized_request for phrase in EXPLICIT_TEST_PHRASES)


def has_test_negation(user_request: str) -> bool:
    """Return True when the request explicitly says not to run tests."""
    normalized_request = user_request.lower()
    return any(phrase in normalized_request for phrase in NEGATED_TEST_PHRASES)
