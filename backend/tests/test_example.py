
"""Example unit tests for the clinical RAG assistant."""
import pytest


class TestExample:
    """Example test class."""

    def test_addition(self):
        """Test basic addition."""
        assert 1 + 1 == 2

    def test_string_concat(self):
        """Test string concatenation."""
        result = "hello" + " " + "world"
        assert result == "hello world"

    def test_list_operations(self):
        """Test list operations."""
        test_list = [1, 2, 3, 4, 5]
        assert len(test_list) == 5
        assert sum(test_list) == 15


class TestCommonScenarios:
    """Test common scenarios."""

    def test_dict_operations(self):
        """Test dictionary operations."""
        test_dict = {"key1": "value1", "key2": "value2"}
        assert test_dict["key1"] == "value1"
        assert len(test_dict) == 2

    def test_boolean_logic(self):
        """Test boolean logic."""
        assert True is True
        assert False is False
        assert (True and False) is False
        assert (True or False) is True
