"""
Tests for the update_values function in iter_helper module.
"""

import pytest
from python_utils.common_utils.iter_helper import update_values


class TestUpdateValuesBasic:
    """Basic functionality tests for update_values"""
    
    def test_update_numbers_in_nested_structure(self):
        """Test updating all numbers in a nested structure"""
        data = [1, [2, 3], {'a': 4}]
        result = update_values(
            lambda x: x * 2 if isinstance(x, (int, float)) else x,
            data
        )
        assert result == [2, [4, 6], {'a': 8}]
    
    def test_convert_strings_to_uppercase(self):
        """Test converting all strings to uppercase"""
        data = {'name': 'alice', 'items': ['apple', 'banana']}
        result = update_values(str.upper, data)
        assert result == {'name': 'ALICE', 'items': ['APPLE', 'BANANA']}
    
    def test_update_nested_dictionaries(self):
        """Test updating nested dictionaries"""
        data = {'a': 1, 'b': {'c': 2, 'd': [3, 4]}}
        result = update_values(
            lambda x: x + 10 if isinstance(x, int) else x,
            data
        )
        assert result == {'a': 11, 'b': {'c': 12, 'd': [13, 14]}}
    
    def test_handle_tuples(self):
        """Test handling tuples (converted to lists)"""
        result = update_values(
            lambda x: x * 2 if isinstance(x, int) else x,
            (1, 2, (3, 4))
        )
        assert result == [2, 4, [6, 8]]
    
    def test_handle_sets(self):
        """Test handling sets (converted to lists)"""
        result = update_values(
            lambda x: x + 1 if isinstance(x, int) else x,
            {1, 2, 3}
        )
        assert sorted(result) == [2, 3, 4]
    
    def test_strings_as_atoms_default(self):
        """Test that strings are treated as atoms by default"""
        result = update_values(str.upper, ['hello', 'world'])
        assert result == ['HELLO', 'WORLD']
    
    def test_handle_none_values(self):
        """Test handling None values"""
        result = update_values(
            lambda x: 'null' if x is None else x,
            [1, None, [2, None]]
        )
        assert result == [1, 'null', [2, 'null']]
    
    def test_complex_nested_structure(self):
        """Test complex nested structure with multiple types"""
        data = {
            'users': [
                {'name': 'alice', 'age': 30},
                {'name': 'bob', 'age': 25}
            ],
            'count': 2
        }
        result = update_values(
            lambda x: x.upper() if isinstance(x, str) else x * 2 if isinstance(x, int) else x,
            data
        )
        expected = {
            'users': [
                {'name': 'ALICE', 'age': 60},
                {'name': 'BOB', 'age': 50}
            ],
            'count': 4
        }
        assert result == expected


class TestUpdateValuesInPlace:
    """Tests for in-place vs copy behavior"""
    
    def test_inplace_update_dict(self):
        """Test in-place update of dict"""
        data = {'a': 1, 'b': [2, 3]}
        original_id = id(data)
        original_list_id = id(data['b'])
        
        result = update_values(
            lambda x: x * 2 if isinstance(x, int) else x,
            data,
            inplace=True
        )
        
        assert result is data
        assert id(result) == original_id
        assert id(result['b']) == original_list_id
        assert data == {'a': 2, 'b': [4, 6]}
    
    def test_inplace_update_list(self):
        """Test in-place update of list"""
        data = [1, 2, [3, 4]]
        original_id = id(data)
        original_nested_id = id(data[2])
        
        result = update_values(
            lambda x: x * 2 if isinstance(x, int) else x,
            data,
            inplace=True
        )
        
        assert result is data
        assert id(result) == original_id
        assert id(result[2]) == original_nested_id
        assert data == [2, 4, [6, 8]]
    
    def test_non_inplace_update(self):
        """Test non-in-place update creates new objects"""
        data = {'a': 1, 'b': [2, 3]}
        original_data = {'a': 1, 'b': [2, 3]}
        
        result = update_values(
            lambda x: x * 2 if isinstance(x, int) else x,
            data,
            inplace=False
        )
        
        assert result is not data
        assert data == original_data  # Original unchanged
        assert result == {'a': 2, 'b': [4, 6]}
    
    def test_inplace_default_behavior(self):
        """Test that inplace=True is the default"""
        data = {'a': 1}
        result = update_values(lambda x: x * 2 if isinstance(x, int) else x, data)
        assert result is data


class TestUpdateValuesAtomTypes:
    """Tests for atom_types parameter"""
    
    def test_default_atom_types(self):
        """Test default atom_types (str,)"""
        result = update_values(str.upper, ['hello', 'world'])
        assert result == ['HELLO', 'WORLD']
    
    def test_strings_as_iterables(self):
        """Test treating strings as iterables"""
        # When strings are not atoms, they get processed as iterables
        # Each character is still a string, so it becomes an atom and gets uppercased
        # This creates infinite recursion, so we need a different approach
        # Instead, test with a function that handles single chars differently
        result = update_values(
            lambda x: x.upper() if isinstance(x, str) and len(x) == 1 else x,
            ['hi'],
            atom_types=()
        )
        # String 'hi' is iterable, so it becomes ['h', 'i'], then each char is uppercased
        assert result == [['H', 'I']]
    
    def test_custom_atom_types_tuple(self):
        """Test custom atom types including tuple"""
        data = {'point': (1, 2), 'values': [3, 4]}
        result = update_values(
            lambda x: x * 2 if isinstance(x, int) else x,
            data,
            atom_types=(str, tuple)
        )
        # Tuple is treated as atom, so not processed
        assert result == {'point': (1, 2), 'values': [6, 8]}
    
    def test_multiple_atom_types(self):
        """Test multiple custom atom types"""
        data = {'text': 'hello', 'nums': (1, 2), 'list': [3, 4]}
        result = update_values(
            lambda x: x * 2 if isinstance(x, int) else x,
            data,
            atom_types=(str, tuple)
        )
        assert result == {'text': 'hello', 'nums': (1, 2), 'list': [6, 8]}


class TestUpdateValuesEdgeCases:
    """Tests for edge cases and special scenarios"""
    
    def test_empty_dict(self):
        """Test with empty dict"""
        result = update_values(lambda x: x, {})
        assert result == {}
    
    def test_empty_list(self):
        """Test with empty list"""
        result = update_values(lambda x: x, [])
        assert result == []
    
    def test_single_value(self):
        """Test with single atomic value"""
        result = update_values(lambda x: x * 2, 5)
        assert result == 10
    
    def test_none_as_input(self):
        """Test with None as input"""
        result = update_values(lambda x: 'null' if x is None else x, None)
        assert result == 'null'
    
    def test_deeply_nested_structure(self):
        """Test with deeply nested structure"""
        data = {'a': {'b': {'c': {'d': 1}}}}
        result = update_values(
            lambda x: x * 10 if isinstance(x, int) else x,
            data
        )
        assert result == {'a': {'b': {'c': {'d': 10}}}}
    
    def test_mixed_types_in_list(self):
        """Test list with mixed types"""
        data = [1, 'hello', 2.5, None, [3, 'world']]
        result = update_values(
            lambda x: x * 2 if isinstance(x, (int, float)) else x,
            data
        )
        assert result == [2, 'hello', 5.0, None, [6, 'world']]
    
    def test_boolean_values(self):
        """Test with boolean values"""
        data = {'flag': True, 'active': False, 'count': 1}
        result = update_values(
            lambda x: not x if isinstance(x, bool) else x * 2 if isinstance(x, int) else x,
            data
        )
        # Note: bool is a subclass of int, so this tests order matters
        assert result == {'flag': False, 'active': True, 'count': 2}
    
    def test_float_values(self):
        """Test with float values"""
        data = {'price': 19.99, 'tax': 1.5, 'items': [10.0, 20.5]}
        result = update_values(
            lambda x: round(x * 1.1, 2) if isinstance(x, float) else x,
            data
        )
        assert result == {'price': 21.99, 'tax': 1.65, 'items': [11.0, 22.55]}


class TestUpdateValuesRealWorld:
    """Real-world use case tests"""
    
    def test_data_normalization(self):
        """Test data normalization use case"""
        form_data = {
            'username': '  Alice  ',
            'email': '  ALICE@EXAMPLE.COM  ',
            'bio': '  Python developer  ',
            'age': 30
        }
        
        def normalize(x):
            if isinstance(x, str):
                return x.strip().lower() if '@' in x else x.strip()
            return x
        
        result = update_values(normalize, form_data, inplace=False)
        assert result == {
            'username': 'Alice',
            'email': 'alice@example.com',
            'bio': 'Python developer',
            'age': 30
        }
    
    def test_unit_conversion(self):
        """Test unit conversion use case"""
        measurements = {
            'height': 1.0,
            'width': 2.0,
            'dimensions': [1.0, 2.0, 3.0],
            'name': 'Box'
        }
        
        def meters_to_feet(x):
            if isinstance(x, (int, float)):
                return round(x * 3.28084, 2)
            return x
        
        result = update_values(meters_to_feet, measurements, inplace=False)
        assert result == {
            'height': 3.28,
            'width': 6.56,
            'dimensions': [3.28, 6.56, 9.84],
            'name': 'Box'
        }
    
    def test_default_value_replacement(self):
        """Test replacing None with default values"""
        config = {
            'timeout': None,
            'retries': 3,
            'settings': {
                'debug': None,
                'verbose': True
            }
        }
        
        defaults = {'timeout': 30, 'debug': False}
        
        def apply_defaults(x):
            if x is None:
                return 0  # Simple default for demo
            return x
        
        result = update_values(apply_defaults, config, inplace=False)
        assert result == {
            'timeout': 0,
            'retries': 3,
            'settings': {
                'debug': 0,
                'verbose': True
            }
        }


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
