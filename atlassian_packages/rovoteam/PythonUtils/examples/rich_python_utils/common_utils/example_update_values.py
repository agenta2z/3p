"""
Example usage of the update_values function from iter_helper.

The update_values function recursively traverses nested data structures and applies
a transformation function to atomic (leaf) values.
"""

from resolve_path import resolve_path
resolve_path()  # Add project src to sys.path

from python_utils.common_utils.iter_helper import update_values


def example_basic_usage():
    """Basic usage examples"""
    print("=" * 60)
    print("BASIC USAGE EXAMPLES")
    print("=" * 60)
    
    # Example 1: Update numbers in nested structure
    print("\n1. Update all numbers (multiply by 2):")
    data = [1, [2, 3], {'a': 4, 'b': [5, 6]}]
    result = update_values(
        lambda x: x * 2 if isinstance(x, (int, float)) else x,
        data
    )
    print(f"   Input:  {[1, [2, 3], {'a': 4, 'b': [5, 6]}]}")
    print(f"   Output: {result}")
    
    # Example 2: Convert strings to uppercase
    print("\n2. Convert all strings to uppercase:")
    data = {'name': 'alice', 'items': ['apple', 'banana', 'cherry']}
    result = update_values(str.upper, data)
    print(f"   Input:  {{'name': 'alice', 'items': ['apple', 'banana', 'cherry']}}")
    print(f"   Output: {result}")
    
    # Example 3: Replace None values
    print("\n3. Replace None with default value:")
    data = {'a': 1, 'b': None, 'c': [2, None, 3]}
    result = update_values(
        lambda x: 0 if x is None else x,
        data
    )
    print(f"   Input:  {{'a': 1, 'b': None, 'c': [2, None, 3]}}")
    print(f"   Output: {result}")


def example_inplace_vs_copy():
    """Demonstrate in-place vs copy behavior"""
    print("\n" + "=" * 60)
    print("IN-PLACE VS COPY BEHAVIOR")
    print("=" * 60)
    
    # In-place update (default)
    print("\n1. In-place update (inplace=True, default):")
    data = {'a': 1, 'b': [2, 3]}
    print(f"   Original: {data}")
    print(f"   Original ID: {id(data)}")
    result = update_values(
        lambda x: x * 10 if isinstance(x, int) else x,
        data,
        inplace=True
    )
    print(f"   Result:   {result}")
    print(f"   Result ID: {id(result)}")
    print(f"   Same object? {result is data}")
    print(f"   Original modified: {data}")
    
    # Copy update
    print("\n2. Copy update (inplace=False):")
    data = {'a': 1, 'b': [2, 3]}
    print(f"   Original: {data}")
    print(f"   Original ID: {id(data)}")
    result = update_values(
        lambda x: x * 10 if isinstance(x, int) else x,
        data,
        inplace=False
    )
    print(f"   Result:   {result}")
    print(f"   Result ID: {id(result)}")
    print(f"   Same object? {result is data}")
    print(f"   Original unchanged: {data}")


def example_complex_transformations():
    """Complex transformation examples"""
    print("\n" + "=" * 60)
    print("COMPLEX TRANSFORMATION EXAMPLES")
    print("=" * 60)
    
    # Example 1: Type-specific transformations
    print("\n1. Multiple type-specific transformations:")
    data = {
        'name': 'alice',
        'age': 30,
        'score': 85.5,
        'active': True,
        'tags': ['python', 'data']
    }
    
    def transform(x):
        if isinstance(x, str):
            return x.upper()
        elif isinstance(x, int):
            return x * 2
        elif isinstance(x, float):
            return round(x, 1)
        else:
            return x
    
    result = update_values(transform, data)
    print(f"   Input:  {data}")
    print(f"   Output: {result}")
    
    # Example 2: Nested user data
    print("\n2. Transform nested user data:")
    users = {
        'users': [
            {'name': 'alice', 'email': 'alice@example.com', 'age': 30},
            {'name': 'bob', 'email': 'bob@example.com', 'age': 25}
        ],
        'count': 2
    }
    
    def sanitize(x):
        if isinstance(x, str) and '@' in x:
            # Mask email
            parts = x.split('@')
            return f"{parts[0][:2]}***@{parts[1]}"
        elif isinstance(x, str):
            return x.title()
        else:
            return x
    
    result = update_values(sanitize, users, inplace=False)
    print(f"   Input:  {users}")
    print(f"   Output: {result}")


def example_atom_types():
    """Demonstrate atom_types parameter"""
    print("\n" + "=" * 60)
    print("ATOM_TYPES PARAMETER")
    print("=" * 60)
    
    # Default: strings are atoms
    print("\n1. Default behavior (strings are atoms):")
    data = ['hello', 'world']
    result = update_values(str.upper, data)
    print(f"   Input:  {data}")
    print(f"   Output: {result}")
    
    # Treat strings as iterables
    print("\n2. Strings as iterables (atom_types=()):")
    data = ['hello']
    result = update_values(str.upper, data, atom_types=())
    print(f"   Input:  {data}")
    print(f"   Output: {result}")
    
    # Custom atom types
    print("\n3. Custom atom types (treat tuples as atoms):")
    data = {'point': (1, 2), 'values': [3, 4]}
    result = update_values(
        lambda x: x * 2 if isinstance(x, int) else x,
        data,
        atom_types=(str, tuple)
    )
    print(f"   Input:  {data}")
    print(f"   Output: {result}")


def example_real_world_use_cases():
    """Real-world use case examples"""
    print("\n" + "=" * 60)
    print("REAL-WORLD USE CASES")
    print("=" * 60)
    
    # Use case 1: Data sanitization
    print("\n1. Data sanitization (remove sensitive info):")
    api_response = {
        'user': {
            'id': 123,
            'name': 'Alice',
            'password': 'secret123',
            'api_key': 'sk-1234567890'
        },
        'settings': {
            'token': 'abc123',
            'public': True
        }
    }
    
    def sanitize_sensitive(x):
        if isinstance(x, str) and any(key in x.lower() for key in ['password', 'secret', 'key', 'token']):
            return '***REDACTED***'
        return x
    
    # Note: This is a simple example - in practice you'd check the key names
    print(f"   Input:  {api_response}")
    print(f"   Output: (simplified - would need key-aware logic)")
    
    # Use case 2: Data normalization
    print("\n2. Data normalization (trim whitespace, lowercase emails):")
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
    print(f"   Input:  {form_data}")
    print(f"   Output: {result}")
    
    # Use case 3: Unit conversion
    print("\n3. Unit conversion (meters to feet):")
    measurements = {
        'height': 1.75,
        'width': 2.5,
        'depth': 0.8,
        'dimensions': [1.0, 2.0, 3.0],
        'name': 'Box'
    }
    
    def meters_to_feet(x):
        if isinstance(x, (int, float)):
            return round(x * 3.28084, 2)
        return x
    
    result = update_values(meters_to_feet, measurements, inplace=False)
    print(f"   Input:  {measurements}")
    print(f"   Output: {result}")


if __name__ == '__main__':
    example_basic_usage()
    example_inplace_vs_copy()
    example_complex_transformations()
    example_atom_types()
    example_real_world_use_cases()
    
    print("\n" + "=" * 60)
    print("✅ All examples completed!")
    print("=" * 60)
